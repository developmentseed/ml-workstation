
# ML Workstation

This goal of this project is to provide a machine learning workstation. This workstation has the following requirements: 
- Easy to deploy and modify settings (memory, etc)
- Easy to restart in case experiment enters a failed state
- Quick to deploy (current workflow of deploying a AMI to EC2 takes too long)
- Should have the following installed:  
    - Julyter lab 
    - GPU enabled PyTorch
    - A Conda environment (possibly multiple conda environments)

# Considered implementations: 
The current workflow, which consists of a pure EC2 instance deployed with a customized AMI takes too long to deploy. Alternatives include: 
- Sagemaker notebook: 
    - The default images are huge and bloated with unnecessary libraries
    - A possible implementation would be to use a custom Sagemaker image, but at that point it essentially the same thing as an EC2 instance (the advantage is that all the networking is handled by Sagemaker - another thing to consider is the cost for a Sagemaker instance with a custom image)
- Fargate based ECS: Fargate deployments have the advantage of handling the networking with an integrated load balancer (enables SSH and HTTP traffice), however they are not yet GPU compatible
- EC2 based ECS: ECS tasks can be deployed from a custom docker image and can be deployed on GPU enabled hardware. The downside is that all of the networking has to be handled manually. This includes an application load balancer to enable HTTP traffic (for accessing the jupter lab instance) and a networkload balancer pointing to the application load balancer to enable SSH traffic (to enable SSH'ing into the instances)

# To deploy: 
```bash
# create virtual environemnt
python3 -m venv <your-env-name>
source <your-env-name>/bin/activate

# upgrade pip and install dependencies
pip instlal --upgrade pip
pip install -r requirements.txt

# set npm version to 18 and install cdk
nvm use 18
npm install -g aws-cdk@2.X

# Optional: verify cdk version
cdk --version

# deploy stack (use the --profile flag if you're using AWS named profiles)
cdk deploy ml-workstation-ecs-<STAGE> --profile <your-named-aws-profile>
```