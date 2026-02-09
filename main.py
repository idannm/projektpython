import boto3
import click
import os
import botocore
import time
import re

# קביעת שם משתמש לטובת תיוג
USERNAME = os.environ.get('USER', 'user')

# === Clients ===
ec2_client = boto3.client('ec2')
s3_client = boto3.client('s3')
r53_client = boto3.client('route53')

@click.group()
def cli():
    """Platform Engineering CLI Tool"""
    pass

# ------------------ EC2 ------------------
@cli.group()
def ec2():
    """Manage EC2 Resources"""
    pass

@ec2.command()
@click.option('--name', required=True)
@click.option('--type', type=click.Choice(['t3.micro','t2.small']), required=True)
def create(name, type):
    try:
        # בדיקת מכסה (Hard Cap) של 2 אינסטנסים רצים
        instances = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:CreatedBy', 'Values': ['platform-cli']},
                {'Name': 'instance-state-name', 'Values': ['running']}
            ]
        )
        running_count = sum(len(r['Instances']) for r in instances['Reservations'])
        
        if running_count >= 2:
            click.echo('Error: Hard cap of 2 running instances reached.')
            return

        # מציאת AMI של אובונטו
        amis = ec2_client.describe_images(
            Filters=[{'Name':'name','Values':['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']}], 
            Owners=['099720109477']
        )
        # מיון לפי תאריך יצירה ושימוש באחרון
        latest_image = sorted(amis['Images'], key=lambda x: x['CreationDate'], reverse=True)[0]['ImageId']

        instance = ec2_client.run_instances(
            ImageId=latest_image, 
            InstanceType=type, 
            MinCount=1, 
            MaxCount=1, 
            TagSpecifications=[{
                'ResourceType':'instance',
                'Tags':[
                    {'Key':'Name','Value':name},
                    {'Key':'CreatedBy','Value':'platform-cli'},
                    {'Key':'Owner','Value':USERNAME}
                ]
            }]
        )
        click.echo(f'Success: Instance {name} created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
def list():
    try:
        instances = ec2_client.describe_instances(Filters=[{'Name':'tag:CreatedBy','Values':['platform-cli']}])
        click.echo(f"{'ID':<20} {'Name':<15} {'State':<10}")
        click.echo("-" * 45)
        for r in instances['Reservations']:
            for i in r['Instances']:
                name = next((t['Value'] for t in i.get('Tags',[]) if t['Key']=='Name'), 'N/A')
                click.echo(f'{i["InstanceId"]:<20} {name:<15} {i["State"]["Name"]:<10}')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
@click.argument('instance_id')
def start(instance_id):
    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
        click.echo(f'Instance {instance_id} started.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@ec2.command()
@click.argument('instance_id')
def stop(instance_id):
    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        click.echo(f'Instance {instance_id} stopped.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

# ------------------ S3 ------------------
@cli.group()
def s3():
    """Manage S3 Buckets"""
    pass

@s3.command()
@click.option('--name', required=True)
@click.option('--public', is_flag=True)
@click.option('--yes', is_flag=True, help="Skip confirmation prompt")
def create(name, public, yes):
    try:
        # --- תיקון וולידציה לשם של באקט ---
        # הופך לאותיות קטנות, מחליף קו תחתון במקף, מסיר רווחים
        original_name = name
        name = name.lower().replace('_', '-').strip()
        
        if original_name != name:
            click.echo(f"Warning: Bucket name sanitized from '{original_name}' to '{name}' to meet AWS rules.")

        # בדיקה שהשם מכיל רק תווים חוקיים
        if not re.match(r'^[a-z0-9.-]+$', name):
            click.echo("Error: Bucket name contains invalid characters even after sanitation. Use only lowercase letters, numbers, and hyphens.")
            return
        # ----------------------------------

        # לוגיקה לאישור באקט ציבורי
        if public and not yes:
            confirm = click.prompt('Are you sure you want a public bucket? (yes/no)')
            if confirm.lower() != 'yes':
                click.echo('Bucket creation cancelled.')
                return

        # --- התיקון לאזורים (Regions) ---
        session = boto3.session.Session()
        current_region = session.region_name
        
        if current_region is None:
            current_region = 'us-east-1'

        if current_region == 'us-east-1':
            s3_client.create_bucket(Bucket=name)
        else:
            s3_client.create_bucket(
                Bucket=name,
                CreateBucketConfiguration={'LocationConstraint': current_region}
            )

        # הוספת תגיות
        s3_client.put_bucket_tagging(
            Bucket=name,
            Tagging={
                'TagSet': [
                    {'Key': 'CreatedBy', 'Value': 'platform-cli'},
                    {'Key': 'Owner', 'Value': USERNAME},
                    {'Key': 'Access', 'Value': 'Public' if public else 'Private'}
                ]
            }
        )
        
        # אם ציבורי - מסירים את ה-Block Public Access
        if public:
            s3_client.delete_public_access_block(Bucket=name)
            
        click.echo(f'Success: Bucket {name} created in {current_region}.')

    except Exception as e:
        click.echo(f"Error: {str(e)}")

@s3.command()
def list():
    try:
        # S3 לא תומך בסינון צד-שרת לפי טאג ב-ListBuckets, אז מסננים בקוד
        all_buckets = s3_client.list_buckets().get('Buckets', [])
        found_any = False
        
        click.echo(f"{'Bucket Name':<30} {'Creation Date'}")
        click.echo("-" * 50)
        
        for b in all_buckets:
            try:
                tags = s3_client.get_bucket_tagging(Bucket=b['Name'])
                tag_set = tags.get('TagSet', [])
                # בודק אם הבאקט נוצר ע"י ה-CLI
                if any(t['Key'] == 'CreatedBy' and t['Value'] == 'platform-cli' for t in tag_set):
                    click.echo(f"{b['Name']:<30} {b['CreationDate']}")
                    found_any = True
            except botocore.exceptions.ClientError:
                continue
        
        if not found_any:
            click.echo("No CLI-created buckets found.")

    except Exception as e:
        click.echo(f"Error: {str(e)}")

@s3.command()
@click.option('--bucket', required=True)
@click.option('--file', required=True)
def upload(bucket, file):
    try:
        # בדיקה האם הבאקט שייך ל-CLI לפני העלאה
        tags = s3_client.get_bucket_tagging(Bucket=bucket)
        tag_set = tags.get('TagSet', [])
        if not any(t['Key'] == 'CreatedBy' and t['Value'] == 'platform-cli' for t in tag_set):
             click.echo("Error: You can only upload to CLI-created buckets.")
             return

        file_name = os.path.basename(file)
        s3_client.upload_file(file, bucket, file_name)
        click.echo(f'Success: File {file_name} uploaded to {bucket}.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

# ------------------ Route53 ------------------
@cli.group()
def r53():
    """Manage Route53 DNS"""
    pass

@r53.command()
@click.option('--name', required=True)
def create(name):
    try:
        ref = f"{name}-{time.time()}" 
        resp = r53_client.create_hosted_zone(
            Name=name, 
            CallerReference=ref, 
            HostedZoneConfig={'Comment':'Created by platform-cli'}
        )
        click.echo(f'Success: Zone {name} created, ID: {resp["HostedZone"]["Id"]}')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@r53.command()
def list():
    try:
        zones = r53_client.list_hosted_zones()['HostedZones']
        click.echo(f"{'Zone Name':<30} {'ID'}")
        click.echo("-" * 50)
        for z in zones:
            if 'Comment' in z.get('Config', {}) and 'platform-cli' in z['Config']['Comment']:
                click.echo(f'{z["Name"]:<30} {z["Id"]}')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

@r53.command(name='create_record')
@click.option('--zone-id', required=True)
@click.option('--name', required=True)
@click.option('--type', required=True, type=click.Choice(['A', 'CNAME', 'TXT']))
@click.option('--value', required=True)
def create_record(zone_id, name, type, value):
    try:
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
        click.echo(f'Success: Record {name} -> {value} created.')
    except Exception as e:
        click.echo(f"Error: {str(e)}")

if __name__=='__main__':
    cli()
