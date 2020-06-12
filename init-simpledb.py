from boto3 import client
from time import sleep

TABLES = ['blacklist', 'alert_status', 'alerts', 'user_responses', 'ignored']

client = client('sdb')

for table in TABLES:
    try:
        client.delete_domain(DomainName='secbot.{}'.format(table))
    except:
        print("Domain 'secbot.{} doesn't exist".format(table))
print("Tables deleted.")

resp = input("Do you want to recreate all tables? ")

if resp == "y":
    sleep(5)

    for table in TABLES:
        client.create_domain(DomainName='secbot.{}'.format(table))

print("Finished.")