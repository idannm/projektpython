import boto3
import click
import os
import botocore
import time
import re

# קביעת שם משתמש לטובת תיוג
USERNAME = os.environ.get('USER', 'user')

# === AWS Clients ===
ec2_client = boto3.client('ec2')
s3_client = boto3.client('s3')
r53_client = boto3.client('route53')

@click.group()
def cli():
    """Platform Engineering CLI Tool - Final Project"""
    pass

# ==========================================
#                   EC2
# ==========================================
@cli.group()
def ec2():
    """Manage EC2 Resources"""
    pass

@ec2.command()
@click.option('--name', required=True, help="Name tag for the instance")
@click.option('--type', type=click.Choice(['t3.micro','t2.small']), required=True, help="Instance type (limited)")
@click.option('--os', type=click.Choice(['ubuntu', 'amazon']), default='ubuntu', help="Operating System choice")
def create(name, type, os):
    """Create a new EC2 instance with limits and OS choice."""
    try:
        # 1. Hard Cap: מקסימום 2 שרתים רצים שלך (idan-cli)
        instances = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:CreatedBy', 'Values': ['idan-cli']},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        running_count = sum(len(r['Instances']) for r in instances['Reservations'])

        if running_count >= 2:
            click.echo('Error: Hard cap of 2 running instances reached. Cannot create more.')
            return

        # 2. מציאת AMI
        if os == 'ubuntu':
            filters = [{'Name':'name','Values':['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']}]
            owners = ['099720109477']
        else:
            filters = [{'Name':'name','Values':['al2023-ami-2023*-x86_64']}]
            owners = ['137112412989']

        amis = ec2_client.describe_images(Filters=filters, Owners=owners)
        if not amis['Images']:
            click.echo(f"Error: No AMI found for {os}.")
            return

        latest_image = sorted(amis['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]['ImageId']

        # 3. יצירת שרת
        ec2_client.run_instances(
            ImageId=latest_image,
            InstanceType=type,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[{
                'ResourceType':'instance',
                'Tags':[
                    {'Key':'Name','Value':name},
                    {'Key':'CreatedBy','Value':'idan-cli'},
                    {'Key':'Owner','Value':USERNAME},
                    {'Key':'OS','Value':os}
                ]
            }]
        )
        click.echo(f'Success: {os} instance "{name}" created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
def list():
    """List only your instances"""
    try:
        instances = ec2_client.describe_instances(Filters=[{'Name':'tag:CreatedBy','Values':['idan-cli']}])
        # התוספת כאן: הוספת OS לכותרות
        click.echo(f"{'ID':<20} {'Name':<20} {'State':<10} {'Type':<10} {'OS':<10}")
        click.echo("-" * 75)
        for r in instances['Reservations']:
            for i in r['Instances']:
                name = next((t['Value'] for t in i.get('Tags',[]) if t['Key']=='Name'), 'N/A')
                # התוספת כאן: שליפת תגית ה-OS
                os_tag = next((t['Value'] for t in i.get('Tags',[]) if t['Key']=='OS'), 'N/A')
                click.echo(f'{i["InstanceId"]:<20} {name:<20} {i["State"]["Name"]:<10} {i["InstanceType"]:<10} {os_tag:<10}')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
@click.argument('instance_id')
def stop(instance_id):
    """Stop your instance"""
    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        click.echo(f'Success: Instance {instance_id} stopped.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
@click.argument('instance_id')
def delete(instance_id):
    """Terminate your instance (Cleanup)"""
    try:
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        click.echo(f'Success: Instance {instance_id} terminated.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

# ==========================================
#                   S3
# ==========================================
@cli.group()
def s3():
    """Manage S3 Resources"""
    pass

@s3.command()
@click.option('--name', required=True)
@click.option('--public', is_flag=True)
@click.option('--yes', is_flag=True)
def create(name, public, yes):
    """Create S3 bucket"""
    try:
        name = name.lower().replace('_', '-').strip()
        if public and not yes:
            if click.prompt('Are you sure you want a public bucket? (yes/no)', default='no') != 'yes':
                click.echo('Cancelled.')
                return

        session = boto3.session.Session()
        region = session.region_name or 'us-east-1'

        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=name)
        else:
            s3_client.create_bucket(Bucket=name, CreateBucketConfiguration={'LocationConstraint': region})

        s3_client.put_bucket_tagging(
            Bucket=name,
            Tagging={'TagSet': [{'Key': 'CreatedBy', 'Value': 'idan-cli'}, {'Key': 'Owner', 'Value': USERNAME}]}
        )
        click.echo(f'Success: Bucket "{name}" created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@s3.command()
def list():
    """List only your buckets"""
    try:
        all_buckets = s3_client.list_buckets().get('Buckets', [])
        found_any = False
        click.echo(f"{'Bucket Name':<40} {'Creation Date'}")
        click.echo("-" * 65)

        for b in all_buckets:
            try:
                tags = s3_client.get_bucket_tagging(Bucket=b['Name'])
                tag_set = tags.get('TagSet', [])
                if any(t['Key'] == 'CreatedBy' and t['Value'] == 'idan-cli' for t in tag_set):
                    click.echo(f"{b['Name']:<40} {b['CreationDate']}")
                    found_any = True
            except botocore.exceptions.ClientError:
                continue

        if not found_any:
            click.echo("No buckets found for idan-cli.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@s3.command()
@click.option('--bucket', required=True)
@click.option('--file', required=True)
def upload(bucket, file):
    """Upload a file to your bucket."""
    try:
        if not os.path.exists(file):
             click.echo(f"Error: Local file '{file}' not found.")
             return

        try:
            tags = s3_client.get_bucket_tagging(Bucket=bucket)
            tag_set = tags.get('TagSet', [])
            if not any(t['Key'] == 'CreatedBy' and t['Value'] == 'idan-cli' for t in tag_set):
                 click.echo("Error: You can only upload to idan-cli buckets.")
                 return
        except botocore.exceptions.ClientError:
             click.echo("Error: Bucket tags not found or bucket does not exist.")
             return

        file_name = os.path.basename(file)
        s3_client.upload_file(file, bucket, file_name)
        click.echo(f'Success: File {file_name} uploaded to {bucket}.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@s3.command()
@click.option('--bucket', required=True)
def delete(bucket):
    """Cleanup: Empty and delete a bucket"""
    try:
        objects = s3_client.list_objects_v2(Bucket=bucket)
        if 'Contents' in objects:
            for obj in objects['Contents']:
                s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
        s3_client.delete_bucket(Bucket=bucket)
        click.echo(f'Success: Bucket {bucket} deleted.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

# ==========================================
#                 Route53
# ==========================================
@cli.group()
def r53():
    """Manage Route53 Resources"""
    pass

@r53.command()
@click.option('--name', required=True)
def create(name):
    """Create a new DNS Hosted Zone"""
    try:
        ref = f"{name}-{time.time()}"
        resp = r53_client.create_hosted_zone(
            Name=name, CallerReference=ref,
            HostedZoneConfig={'Comment':'Created by idan-cli'}
        )
        click.echo(f'Success: Hosted Zone "{name}" created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@r53.command()
def list():
    """List Hosted Zones created by this CLI."""
    try:
        zones = r53_client.list_hosted_zones()['HostedZones']
        click.echo(f"{'Zone Name':<30} {'ID'}")
        click.echo("-" * 50)
        found = False
        for z in zones:
            if 'Comment' in z.get('Config', {}) and 'idan-cli' in z['Config']['Comment']:
                click.echo(f'{z["Name"]:<30} {z["Id"]}')
                found = True
        if not found:
            click.echo("No idan-cli zones found.")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@r53.command()
@click.option('--zone-id', required=True)
@click.option('--name', required=True)
@click.option('--type', type=click.Choice(['A', 'CNAME']), default='A')
@click.option('--value', required=True)
def create_record(zone_id, name, type, value):
    """Create a DNS record"""
    try:
        r53_client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch={'Changes':[{
                'Action':'UPSERT',
                'ResourceRecordSet':{
                    'Name':name, 'Type':type, 'TTL':300,
                    'ResourceRecords':[{'Value':value}]
                }
            }]}
        )
        click.echo(f'Success: Record {name} -> {value} created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

if __name__ == '__main__':
    cli()
