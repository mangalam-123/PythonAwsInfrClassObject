
import boto3
from botocore.exceptions import ClientError

with open('base64.txt', 'r') as fp:
    USERDATA = fp.read()

class AwsVpcNetwork(object):
    def __init__(self, vpc_resource, vpc_client, rds_client):
        self.vpc_resource = vpc_resource
        self.vpc_client = vpc_client
        self.rds_client = rds_client

    def create_custom_vpc(self):

        response = self.vpc_resource.create_vpc(CidrBlock="10.230.0.0/16",
                                                InstanceTenancy="default",
                                                TagSpecifications=[{
                                                    'ResourceType': 'vpc',
                                                    'Tags':[{
                                                            'Key': 'Name',
                                                            'Value': 'Edf_vpc'
                                                    }]
                                                }])

    def describe_vpc(self):

        vpc_id = ""
        response = self.vpc_client.describe_vpcs()
        for vpc in response['Vpcs']:
            if vpc["Tags"][0]["Value"].__contains__("Edf_vpc"):
                vpc_id = vpc["VpcId"]
                break;
        return vpc_id


    def create_subnets(self, vpc_id):

        subnet_name = ['public-subnet-1', 'private-subnet-1', 'db-subnet-1']
        subnet_cidr = ["10.230.0.0/26", "10.230.0.64/26", "10.230.0.128/26"]
        az = ['ap-south-1a', 'ap-south-1b', 'ap-south-1c']
        index = 0
        for subnet in subnet_cidr:
            response = self.vpc_resource.create_subnet(CidrBlock=subnet,
                                                       TagSpecifications=[{
                                                           'ResourceType': 'subnet',
                                                           'Tags':[{
                                                               'Key': 'Name',
                                                               'Value': subnet_name[index]
                                                           }]
                                                       }], VpcId=vpc_id, AvailabilityZone=az[index])

            index +=1

    def describe_subnets(self, vpc_id):

        public_subnetid = ""
        private_subnetid = ""
        db_subnetid = ""

        response = self.vpc_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        for subnet in response['Subnets']:
            if subnet["Tags"][0]["Value"].__contains__("public-subnet-1"):
                public_subnetid = subnet["SubnetId"]
                response = self.vpc_client.modify_subnet_attribute(MapPublicIpOnLaunch={'Value': True}, SubnetId=public_subnetid)
            elif subnet["Tags"][0]["Value"].__contains__("private-subnet-1"):
                private_subnetid = subnet['SubnetId']
            else:
                db_subnetid = subnet["SubnetId"]


        return public_subnetid, private_subnetid, db_subnetid

    def create_igw(self, vpc_id):

        response = self.vpc_resource.create_internet_gateway(TagSpecifications=[{
                                                                'ResourceType': 'internet-gateway',
                                                                 'Tags':[{
                                                                     'Key': 'Name',
                                                                      'Value': 'Edf-Igw'
                                                                 }]
        }])

    def describe_igw(self):

        igw_id = ""
        response = self.vpc_client.describe_internet_gateways()
        for igw in response['InternetGateways']:
            if igw["Tags"][0]["Value"].__contains__("Edf-Igw"):
                igw_id = igw["InternetGatewayId"]
                break;
        return igw_id

    def attach_igw_vpc(self, vpc_id, igw_id):

        response = self.vpc_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

    def create_route_table(self, vpc_id):

        rt_name = ['public_rt', 'private_rt']

        for rt in rt_name:
            response = self.vpc_resource.create_route_table(TagSpecifications=[{
                    'ResourceType': 'route-table',
                    'Tags': [{
                        'Key': 'Name',
                        'Value': rt
                    }]
            }], VpcId = vpc_id)

    def describe_rt(self, vpc_id):

        pub_rtid = ""
        prvt_rdid = ""
        response = self.vpc_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        print(response)
        for rt in response["RouteTables"]:
            if rt["Tags"][0]["Value"].__contains__("public_rt"):
                pub_rtid = rt["RouteTableId"]
            elif rt["Tags"][0]["Value"].__contains__("private_rt"):
                prvt_rdid = rt["RouteTableId"]

        return pub_rtid, prvt_rdid

    def create_route(self, vpc_id, pub_rtid, igw_id):

        response = self.vpc_client.create_route(DestinationCidrBlock="0.0.0.0/0",
                                                  GatewayId=igw_id,RouteTableId=pub_rtid)

    def associate_pub_rt_subnet(self, pub_subid, pub_rtid):

        resource = self.vpc_client.associate_route_table(RouteTableId=pub_rtid, SubnetId=pub_subid)

    def associate_prvt_rt_subnet(self, prvt_subid,db_subid, prvt_rtid):

        resource = self.vpc_client.associate_route_table(RouteTableId=prvt_rtid, SubnetId=prvt_subid)
        resource = self.vpc_client.associate_route_table(RouteTableId=prvt_rtid, SubnetId=db_subid)

    def create_ec2_sg(self, vpc_id):
        try:
            sg_name = "ec2-sg"
            response = self.vpc_client.create_security_group(
                GroupName=sg_name,
                VpcId=vpc_id,
                Description="This is my custom ec2-sg"
            )
            print(response)
            sg_id = response["GroupId"]
            response = self.vpc_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[{
                    'IpProtocol': 'tcp',
                    'ToPort': 22,
                    'FromPort': 22,
                    'IpRanges':[{'CidrIp': '0.0.0.0/0'}]
                },
                    {
                        'IpProtocol': 'tcp',
                        'ToPort': 80,
                        'FromPort': 80,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'ToPort': 443,
                        'FromPort': 443,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    }
                ]
            )
        except Exception as e:
            if str(e).__contains__("already exists"):
                response = vpc_client.describe_security_groups(Filters=[{
                    'Name': 'vpc-id', 'Values': [vpc_id]
                }, {'Name': 'group-name', 'Values': [sg_name]}])
                sg_id = response["SecurityGroups"][0]["GroupId"]
                return sg_id, sg_name
            else:
                return sg_id, sg_name



    def create_db_sg(self, vpc_id):
        db_sgname = "db-sg"
        try:
            response = self.vpc_client.create_security_group(
                GroupName=db_sgname,
                VpcId=vpc_id,
                Description="This is the sg for db"
            )

            db_sgid = response["GroupId"]

            response = self.vpc_client.authorize_security_group_ingress(
                GroupId=db_sgid,
                IpPermissions=[{
                'IpProtocol': 'tcp',
                'ToPort': 3306,
                'FromPort': 3306,
                'IpRanges':[{'CidrIp': '0.0.0.0/0'}]
            }]
            )

        except Exception as e:
            if str(e).__contains__("already exists"):
                response = self.vpc_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]},
                                                                            {'Name': 'group-name', 'Values': [db_sgname]}])
                db_sgid = response["SecurityGroups"][0]["GroupId"]
                return db_sgid, db_sgname
            else:
                return db_sgid, db_sgname

    def create_key_pair(self, vpc_id):

        key_name = "my-python"
        private_key = ""

        response = self.vpc_client.create_key_pair(KeyName=key_name)
        private_key = response["KeyMaterial"]
        with open('key_file.pem', 'w') as fp:
            fp.write(str(private_key))

    def create_instance(self, vpc_id, pub_subid, sg_id):

        response = self.vpc_client.run_instances(
            ImageId="ami-0e6329e222e662a52",
            InstanceType="t2.micro",
            MaxCount=1,
            MinCount=1,
            KeyName="my-python",
            SecurityGroupIds=[sg_id],
            SubnetId= pub_subid,
            UserData=USERDATA,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{
                    'Key': 'Name',
                    'Value': 'Ec2-Instance'
                }]
            }]
        )

    def create_db_subnet(self, vpc_id, prvt_subid, db_subid):

        response = self.rds_client.create_db_subnet_group(
            DBSubnetGroupName="my-db-sub-group",
            DBSubnetGroupDescription="My-prvt-db-subnet-grp",
            SubnetIds=[
                prvt_subid,
                db_subid
            ]
        )

    def create_db_instance(self, vpc_id, db_sgid):

        response = self.rds_client.create_db_instance(
            DBInstanceIdentifier="Custom-db",
            AllocatedStorage=20,
            DBInstanceClass="db.t2.micro",
            Engine="MySQL",
            EngineVersion="8.0.28",
            VpcSecurityGroupIds=[db_sgid],
            MasterUsername="admin",
            MasterUserPassword="admin123",
            DBSubnetGroupName="my-db-sub-group",
            MultiAZ= False,
            PubliclyAccessible=False

        )

if __name__ == '__main__':
    try:
        vpc_resource = boto3.resource('ec2', region_name="ap-south-1")
        rds_client = boto3.client("rds", region_name="ap-south-1")
        vpc_client = boto3.client('ec2',region_name="ap-south-1" )
        call_obj = AwsVpcNetwork(vpc_resource, vpc_client, rds_client)
        # call_obj.create_custom_vpc()
        vpc_id = call_obj.describe_vpc()
        # call_obj.create_subnets(vpc_id)
        pub_subid, prvt_subid, db_subid = call_obj.describe_subnets(vpc_id)
        # print(f"{pub_subid}, {prvt_subid}, {db_subid}")
        # call_obj.create_igw(vpc_id)
        igw_id = call_obj.describe_igw()
        # call_obj.attach_igw_vpc(vpc_id,igw_id)
        # call_obj.create_route_table(vpc_id)
        pub_rtid, prvt_rtid = call_obj.describe_rt(vpc_id)
        # call_obj.create_route(vpc_id, pub_rtid, igw_id)
        # call_obj.associate_rt_subnet(pub_subid, pub_rtid)
        # call_obj.associate_prvt_rt_subnet(prvt_subid, db_subid, prvt_rtid)
        sg_id, sg_name = call_obj.create_ec2_sg(vpc_id)
        print(sg_id, sg_name)
        db_sgid, db_sgname = call_obj.create_db_sg(vpc_id)
        print(db_sgid, db_sgname)
        # call_obj.create_key_pair(vpc_id)
        # call_obj.create_instance(vpc_id, pub_subid, sg_id)
        call_obj.create_db_instance(vpc_id, db_sgid)
    except ClientError as e:
        print(e)
