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

# Create and attach an Internet Gateway so the VPC can access the internet
igw_response = ec2.create_internet_gateway(
    TagSpecifications=[
        {
            "ResourceType": "internet-gateway",
            "Tags": [
                {"Key": "Name", "Value": "pf1-igw"}
            ]
        }
    ]
)
igw_id = igw_response["InternetGateway"]["InternetGatewayId"]
ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
print("Internet Gateway created and attached:", igw_id)

# Get available AZs
azs = ec2.describe_availability_zones()["AvailabilityZones"]

# Create first subnet in one AZ with a specific CIDR block (subset of VPC CIDR)
subnet_1 = ec2.create_subnet(
    VpcId=vpc_id,
    CidrBlock="10.0.1.0/24",
    AvailabilityZone=azs[0]["ZoneName"]
)

# Create second subnet in same AZ with a different CIDR block
subnet_2 = ec2.create_subnet(
    VpcId=vpc_id,
    CidrBlock="10.0.2.0/24",
    AvailabilityZone=azs[0]["ZoneName"]
)

subnet_1_id = subnet_1["Subnet"]["SubnetId"]
subnet_2_id = subnet_2["Subnet"]["SubnetId"]

print("Subnets:", subnet_1_id, subnet_2_id)

ec2.create_tags(
    Resources=[subnet_1_id],
    Tags=[
        {"Key": "Name", "Value": "pf1-subnet-1"},
        {"Key": "Tier", "Value": "public"},
    ],
)
ec2.create_tags(
    Resources=[subnet_2_id],
    Tags=[
        {"Key": "Name", "Value": "pf1-subnet-2"},
        {"Key": "Tier", "Value": "private"},
    ],
)

# Create a route table for the public subnet and route internet traffic via the IGW
public_rt = ec2.create_route_table(
    VpcId=vpc_id,
    TagSpecifications=[
        {
            "ResourceType": "route-table",
            "Tags": [
                {"Key": "Name", "Value": "pf1-public-rt"}
            ]
        }
    ],
)
public_rt_id = public_rt["RouteTable"]["RouteTableId"]
ec2.create_route(
    RouteTableId=public_rt_id,
    DestinationCidrBlock="0.0.0.0/0",
    GatewayId=igw_id,
)
ec2.associate_route_table(
    RouteTableId=public_rt_id,
    SubnetId=subnet_1_id,
)
print("Public route table created and associated with subnet_1:", public_rt_id)

# Security group for resources in subnet_1 to allow public access (SSH/HTTP/HTTPS)
public_sg = ec2.create_security_group(
    GroupName="pf1-public-sg",
    Description="Public access for subnet_1 resources",
    VpcId=vpc_id,
    TagSpecifications=[
        {
            "ResourceType": "security-group",
            "Tags": [
                {"Key": "Name", "Value": "pf1-public-sg"}
            ]
        }
    ]
)
public_sg_id = public_sg["GroupId"]
ec2.authorize_security_group_ingress(
    GroupId=public_sg_id,
    IpPermissions=[
        {
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH from internet"}],
        },
        {
            "IpProtocol": "tcp",
            "FromPort": 80,
            "ToPort": 80,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP from internet"}],
        },
        {
            "IpProtocol": "tcp",
            "FromPort": 443,
            "ToPort": 443,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTPS from internet"}],
        },
    ],
)
print("Public security group created:", public_sg_id)

ec2.modify_subnet_attribute(
    SubnetId=subnet_1_id,
    MapPublicIpOnLaunch={"Value": True}
)
print("Configured subnet_1 for public IP assignment.")

# deploy a NAT Gateway in subnet_1
eip_1 = ec2.allocate_address(Domain="vpc")
nat_1 = ec2.create_nat_gateway(
    SubnetId=subnet_1_id,
    AllocationId=eip_1["AllocationId"],
    TagSpecifications=[
        {
            "ResourceType": "natgateway",
            "Tags": [
                {"Key": "Name", "Value": "pf1-nat-1"}
            ]
        }
    ]
)


print(
    "NAT Gateways requested:",
    nat_1["NatGateway"]["NatGatewayId"]
)
