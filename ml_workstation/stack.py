from . import config

from constructs import Construct

from aws_cdk import Stack
from aws_cdk import aws_ec2, aws_ecs, aws_logs
from aws_cdk import aws_elasticloadbalancingv2 as aws_lb


class MlWorkstationEcsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = aws_ec2.Vpc(self, "vpc", max_azs=2, nat_gateways=1)

        log_driver = aws_ecs.AwsLogDriver(
            stream_prefix=f"{config.PROJECT_NAME}/{config.STAGE}",
            log_retention=aws_logs.RetentionDays.ONE_WEEK,
        )

        task_definition = aws_ecs.Ec2TaskDefinition(
            self, "task-denfinition", network_mode=aws_ecs.NetworkMode.AWS_VPC
        )

        task_definition.add_container(
            "container",
            image=aws_ecs.ContainerImage.from_registry("pangeo/pytorch-notebook"),
            command=["jupyter", "lab"],
            gpu_count=1,
            port_mappings=[
                aws_ecs.PortMapping(container_port=8080, host_port=8080),
                aws_ecs.PortMapping(container_port=22, host_port=22),
            ],
            logging=log_driver,
            memory_reservation_mib=1024,
        )

        cluster = aws_ecs.Cluster(self, "cluster", container_insights=True, vpc=vpc)
        cluster.add_capacity(
            "default-autoscaling-capacity",
            instance_type=aws_ec2.InstanceType("p2.8xlarge"),
            desired_capacity=1,
            min_capacity=1,
            max_capacity=1,
            # associate_public_ip_address=True,
            # vpc_subnets=aws_ec2.SubnetSelection(
            #     subnet_type=aws_ec2.SubnetType.PRIVATE_WITH_EGRESS
            # ),
        )

        service = aws_ecs.Ec2Service(
            self,
            "ecs-service",
            cluster=cluster,
            task_definition=task_definition,
            # assign_public_ip=True,
            # daemon ensures one task per container
            daemon=True,
        )

        alb = aws_lb.ApplicationLoadBalancer(
            self, "load-balancer", vpc=vpc, internet_facing=True
        )
        listener = alb.add_listener("alb-public-listener", port=80, open=True)
        listener.add_targets(
            "ecs-listener-target",
            port=8080,
            targets=[
                service.load_balancer_target(
                    container_name="container", container_port=8080
                )
            ],
        )
