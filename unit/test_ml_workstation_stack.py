import aws_cdk as core
import aws_cdk.assertions as assertions

from ml_workstation.stack import MlWorkstationEcsStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ml_workstation/stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MlWorkstationEcsStack(app, "ml-workstation-ecs")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
