from . import config

import urllib.request
from constructs import Construct

from aws_cdk import Stack, RemovalPolicy
from aws_cdk import aws_ec2, aws_ecs, aws_logs, aws_kms, aws_efs
from aws_cdk import aws_ecs_patterns


class MlWorkstationEcsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = aws_ec2.Vpc(self, "vpc", max_azs=2, nat_gateways=1)

        # Open ingress to the deploying computer public IP

        jupyter_efs_security_group = aws_ec2.SecurityGroup(
            self,
            "elastic-file-server-security-group",
            vpc=vpc,
            description="Jupyter shared filesystem security group",
            allow_all_outbound=True,
        )

        efs_cmk = aws_kms.Key(
            self,
            "efs-custom-master-key",
            description="CMK for EFS Encryption",
            enabled=True,
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        efs = aws_efs.FileSystem(
            self,
            "elastic-file-system",
            vpc=vpc,
            vpc_subnets=aws_ec2.SubnetSelection(
                subnet_type=aws_ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_group=jupyter_efs_security_group,
            removal_policy=RemovalPolicy.DESTROY,
            encrypted=True,
            kms_key=efs_cmk,
        )

        efs_mount_point = aws_ecs.MountPoint(
            container_path="/home", source_volume="efs-volume", read_only=False
        )

        log_driver = aws_ecs.AwsLogDriver(
            stream_prefix=f"{config.PROJECT_NAME}/{config.STAGE}",
            log_retention=aws_logs.RetentionDays.ONE_WEEK,
        )

        task_definition = aws_ecs.Ec2TaskDefinition(
            self, "task-denfinition", network_mode=aws_ecs.NetworkMode.AWS_VPC
        )

        task_definition.add_volume(
            name="efs-volume",
            efs_volume_configuration=aws_ecs.EfsVolumeConfiguration(
                file_system_id=efs.file_system_id
            ),
        )

        container = task_definition.add_container(
            "container",
            image=aws_ecs.ContainerImage.from_registry("pangeo/pytorch-notebook"),
            command=[
                "jupyter",
                "lab",
                "--no-browser",
                "--ip=0.0.0.0",
                f"--ServerApp.password={config.JUPYTER_LAB_PASSWORD}",
            ],
            gpu_count=1,
            port_mappings=[
                aws_ecs.PortMapping(container_port=8888, host_port=8888),
                # aws_ecs.PortMapping(container_port=22, host_port=22),
            ],
            logging=log_driver,
            memory_reservation_mib=1024,
        )

        container.add_mount_points(efs_mount_point)

        cluster = aws_ecs.Cluster(self, "cluster", container_insights=True, vpc=vpc)

        cluster.add_capacity(
            "default-autoscaling-capacity",
            instance_type=aws_ec2.InstanceType("p2.xlarge"),
            machine_image=aws_ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=aws_ecs.AmiHardwareType.GPU
            ),
            desired_capacity=1,
            min_capacity=1,
            max_capacity=1,
            # associate_public_ip_address=True,
            # vpc_subnets=aws_ec2.SubnetSelection(subnet_type=aws_ec2.SubnetType.PUBLIC),
        )

        ecs_service = aws_ecs_patterns.ApplicationLoadBalancedEc2Service(
            scope=self,
            id="ecs-service",
            cluster=cluster,
            task_definition=task_definition,
            # public_load_balancer=True,
        )

        # SET SECURITY GROUP WITH 8000 FOR HTTP
        ecs_service.service.connections.security_groups[0].add_ingress_rule(
            peer=aws_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=aws_ec2.Port.tcp(8888),
            description="Allow inbound from VPC",
        )

        my_ip_cidr = (
            urllib.request.urlopen("http://checkip.amazonaws.com")
            .read()
            .decode("utf-8")
            .strip()
            + "/32"
        )

        ecs_service.service.connections.security_groups[0].add_ingress_rule(
            peer=aws_ec2.Peer.ipv4(my_ip_cidr),
            connection=aws_ec2.Port.tcp(8888),
            description="Allow inbound from VPC",
        )

        jupyter_efs_security_group.connections.allow_from(
            ecs_service.service.connections.security_groups[0],
            port_range=aws_ec2.Port.tcp(2049),
            description="Allow NFS from ECS Service containers",
        )

        ecs_service.target_group.configure_health_check(
            path="/", healthy_http_codes="200-302", port="8888"
        )
