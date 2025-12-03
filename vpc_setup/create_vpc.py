import boto3

# Create VPC
ec2 = boto3.client("ec2", region_name="eu-central-1") 

response = ec2.create_vpc(
    CidrBlock="10.0.0.0/16",
    TagSpecifications=[
        {
            "ResourceType": "vpc",
            "Tags": [
                {"Key": "Name", "Value": "pf1-vpc"}
            ]
        }
    ]
)

vpc_id = response["Vpc"]["VpcId"]
print("VPC created:", vpc_id)

# Enable DNS support and hostnames
ec2.modify_vpc_attribute(
    VpcId=vpc_id,
    EnableDnsSupport={"Value": True}
)

ec2.modify_vpc_attribute(
    VpcId=vpc_id,
    EnableDnsHostnames={"Value": True}
)

print("DNS enabled")

# Get available AZs
azs = ec2.describe_availability_zones()["AvailabilityZones"]

subnet_1 = ec2.create_subnet(
    VpcId=vpc_id,
    CidrBlock="10.0.1.0/24",
    AvailabilityZone=azs[0]["ZoneName"]
)

subnet_2 = ec2.create_subnet(
    VpcId=vpc_id,
    CidrBlock="10.0.2.0/24",
    AvailabilityZone=azs[1]["ZoneName"]
)

subnet_1_id = subnet_1["Subnet"]["SubnetId"]
subnet_2_id = subnet_2["Subnet"]["SubnetId"]

print("Subnets:", subnet_1_id, subnet_2_id)

