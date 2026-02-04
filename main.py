import boto3
import click
import os

USERNAME = os.environ.get('USER', 'idanmusahaev')

# === EC2 ===
ec2_client = boto3.client('ec2')

# === S3 ===
s3_client = boto3.client('s3')

# === Route53 ===
r53_client = boto3.client('route53')

@click.group()
def cli():
    pass

# ------------------ EC2 ------------------
@cli.group()
def ec2():
    pass

@ec2.command()
@click.option('--name', required=True)
@click.option('--type', type=click.Choice(['t3.micro','t2.small']), required=True)
def create(name,type):
    # חיפוש מספר instances קיימים
    instances = ec2_client.describe_instances(Filters=[{'Name':'tag:CreatedBy','Values':['platform-cli']}])
    running_count = sum(1 for r in instances['Reservations'] for i in r['Instances'] if i['State']['Name']=='running')
    if running_count >=2:
        click.echo('Hard cap of 2 running instances reached.')
        return

    # בוחר AMI
    amis = ec2_client.describe_images(Filters=[{'Name':'name','Values':['ubuntu/images/hvm-ssd/ubuntu-*-22.04-amd64-server-*']}], Owners=['099720109477'])
    latest_image = sorted(amis['Images'], key=lambda x:x['CreationDate'], reverse=True)[0]['ImageId']

    instance = ec2_client.run_instances(ImageId=latest_image, InstanceType=type, MinCount=1, MaxCount=1, TagSpecifications=[{'ResourceType':'instance','Tags':[{'Key':'Name','Value':name},{'Key':'CreatedBy','Value':'platform-cli'},{'Key':'Owner','Value':USERNAME}]}])
    click.echo(f'Instance {name} created, ID: {instance["Instances"][0]["InstanceId"]}')

@ec2.command()
def list():
    instances = ec2_client.describe_instances(Filters=[{'Name':'tag:CreatedBy','Values':['platform-cli']}])
    click.echo('ID\tName\tState')
    for r in instances['Reservations']:
        for i in r['Instances']:
            name = next((t['Value'] for t in i.get('Tags',[]) if t['Key']=='Name'), 'N/A')
            click.echo(f'{i["InstanceId"]}\t{name}\t{i["State"]["Name"]}')

@ec2.command()
@click.argument('instance_id')
def start(instance_id):
    ec2_client.start_instances(InstanceIds=[instance_id])
    click.echo(f'Instance {instance_id} started.')

@ec2.command()
@click.argument('instance_id')
def stop(instance_id):
    ec2_client.stop_instances(InstanceIds=[instance_id])
    click.echo(f'Instance {instance_id} stopped.')

# ------------------ S3 ------------------
@cli.group()
def s3():
    pass

@s3.command()
@click.option('--name', required=True)
@click.option('--public', is_flag=True)
def create(name, public):
    if public:
        confirm = click.prompt('Are you sure you want a public bucket? (yes/no)')
        if confirm.lower() != 'yes':
            click.echo('Bucket creation cancelled.')
            return
    s3_client.create_bucket(Bucket=name)
    click.echo(f'Bucket {name} created.')

@s3.command()
def list():
    buckets = s3_client.list_buckets()
    for b in buckets['Buckets']:
        click.echo(b['Name'])

# ------------------ Route53 ------------------
@cli.group()
def r53():
    pass

@r53.command()
@click.option('--name', required=True)
def create(name):
    resp = r53_client.create_hosted_zone(Name=name, CallerReference=name, HostedZoneConfig={'Comment':'Created by platform-cli'})
    click.echo(f'Route53 zone {name} created, ID: {resp["HostedZone"]["Id"]}')

@r53.command()
def list():
    zones = r53_client.list_hosted_zones()['HostedZones']
    for z in zones:
        if z.get('Config',{}).get('Comment','').find('platform-cli')>=0:
            click.echo(f'{z["Name"]} | ID: {z["Id"]}')

@r53.command()
@click.option('--zone-id', required=True)
@click.option('--name', required=True)
@click.option('--type', required=True)
@click.option('--value', required=True)
def create_record(zone_id, name, type, value):
    r53_client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Changes':[{
                'Action':'UPSERT',
                'ResourceRecordSet':{
                    'Name':name,
                    'Type':type,
                    'TTL':300,
                    'ResourceRecords':[{'Value':value}]
                }
            }]
        }
    )
    click.echo(f'Record {name} -> {value} created in zone {zone_id}')

if __name__=='__main__':
    cli()
