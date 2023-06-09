from . import config
from . import utils

from constructs import Construct
from aws_cdk import Stack, RemovalPolicy, CfnOutput
from aws_cdk import aws_ec2, aws_ecs, aws_logs, aws_kms, aws_efs, aws_autoscaling
from aws_cdk import aws_ecs_patterns


class MlWorkstationEcsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfn_keypair = aws_ec2.CfnKeyPair(
            self,
            "ssh-key-pair",
            key_name=construct_id,
            key_type="rsa",
        )

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
            ],
            logging=log_driver,
            memory_reservation_mib=1024,
            health_check=aws_ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://127.0.0.1:8888/ || exit 1"]
            ),
        )

        container.add_mount_points(efs_mount_point)

        cluster = aws_ecs.Cluster(self, "cluster", container_insights=True, vpc=vpc)

        auto_scaling_group = aws_autoscaling.AutoScalingGroup(
            self,
            "autoscaling-group",
            vpc=vpc,
            instance_type=aws_ec2.InstanceType("p2.xlarge"),
            machine_image=aws_ecs.EcsOptimizedImage.amazon_linux2(
                hardware_type=aws_ecs.AmiHardwareType.GPU
            ),
            desired_capacity=0,
            min_capacity=0,
            max_capacity=1,
            associate_public_ip_address=True,
            vpc_subnets=aws_ec2.SubnetSelection(subnet_type=aws_ec2.SubnetType.PUBLIC),
            key_name=cfn_keypair.key_name,
        )
        auto_scaling_group.node.add_dependency(vpc)

        capacity_provider = aws_ecs.AsgCapacityProvider(
            self,
            "asg-capacity-provider",
            auto_scaling_group=auto_scaling_group,
            # ensures that resource's termination protenction doesn't block the stack
            # from deleting
            enable_managed_termination_protection=False,
        )
        cluster.add_asg_capacity_provider(capacity_provider)

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
            description="Allow inbound from VPC to PRIVATE security group",
        )
        auto_scaling_group.connections.security_groups[0].add_ingress_rule(
            peer=aws_ec2.Peer.ipv4(utils.get_public_ip()),
            connection=aws_ec2.Port.tcp(22),
            description="Allow inbound from local machine to PUBLIC security group",
        )

        jupyter_efs_security_group.connections.allow_from(
            ecs_service.service.connections.security_groups[0],
            port_range=aws_ec2.Port.tcp(2049),
            description="Allow NFS from ECS Service containers",
        )

        ecs_service.target_group.configure_health_check(
            path="/", healthy_http_codes="200-302", port="8888"
        )

        # TODO: add output with ssh info for container (public IP/DNS etc)
        CfnOutput(
            self,
            id="retrieve-private-key-command",
            value=f'aws ssm get-parameter --name /ec2/keypair/{cfn_keypair.attr_key_pair_id} --query "Parameter.Value" --with-decryption --output text --profile dev-seed > {cfn_keypair.key_name}.pem',
        )

        # NOTES for deploying updates:

        # Make sure aws cli is upgraded aws-cli/2.7.6
        # https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

        # Make sure private key has correct permissions:
        # chmod 400 ml-workstation-ecs-prod.pem

        # STOP ECS tasks before running cdk-deploy:
        # There is somethign where the deployment waits for tasks to STOP before running updates to the service

        # AutoScaling Group Capacity provider blocks stack deletion

        # EC2 instance still charges through AutoScaling Group, even when task is stopped from ECS console
        # To ensure the EC2 instances get stopped, set the `desired_count` property in the AutoScaling Group
        # to 0.
