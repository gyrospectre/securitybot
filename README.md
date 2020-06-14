# Securitybot
### Distributed alerting for the masses!
A fork of the famous [Dropbox Security Bot][db-orig], which is no longer maintained and getting a bit long in the tooth! It's been given a fresh coat of paint,
via [Antoine Cardon][algolia] who did some great work a few years ago with Python3 conversion and some extra cleanup. 

Securitybot is an open-source implementation of a distributed alerting chat bot, as described in Ryan Huber's [blog post][slack-blog].
Distributed alerting improves the monitoring efficiency of your security team and can help you catch security incidents faster and more efficiently.

### What has changed?
A lot!
- Heaps of cleanup, making the project much more modular, which makes adding new chat/db/auth providers easier.
- Slack: Moved to the new(er) Slack v2 SDK, which changed significantly from v1, and updated to use the Conversations API in readiness for deprecation of the
  old functions in early 2021.
- Secrets Management: Moved off hardcoded secrets, and added support for storing secrets in vault solutions. Initial support for Hashicorp Vault and AWS Secrets Manager.
- Auth: Added support for Okta as an auth provider, building on [Chandler Newby][mew1033]'s initial work. Note that Duo is now broken, as I don't have access to a Duo
  account to test and fix.
- Database: Abstracted the database, and added support for AWS SimpleDB as a MySQL alternative. The database is now initialised by SecurityBot at runtime, if needed. This
  makes initial setup quicker and easier.
- Vagrant: (Mostly) automated setup of a dev environment using Vagrant. Again, focus on easy quickstart.

## Quick Start
Install vagrant and virtualbox on your dev machine. Then, deploy the code into a VM:
```
git clone https://github.com/gyrospectre/securitybot.git
cd securitybot
vagrant up
```
Vagrant will spin up an Ubuntu VM, install MySQL, and install python deps. Next, you need to setup your config.
All config is handled by `config/bot.yaml`. Choose the providers you want to use and pop them into the config yaml.
```
vagrant ssh
cd /vagrant
vi config/bot.yaml
```

### Auth
An authentication provider is used to verify when a user says they performed an action. Since their account may have been compromised, and an attacker responding
to the message, we'll use a MFA push to validate the response actually came from the user.

Choices are Okta, Duo (borked!), or NullAuth. The latter basically disables auth if you don't have Okta and want to play.
- Okta : You'll need an API token. I used a read-only admin level token; you should be able to use a less powerful account but will have to play to work out 
how low you can go in least privilege and still maintain SecurityBot functionality.
You'll also need the `base_url` for your account, in the form of `https://XXXXXX.okta.com`

- Duo : Broken, don't use. Would love someone with access to a Duo account to fix and cut a PR!

- NullAuth : A dummy auth provider to test with if you don't have Okta or Duo. No provider specific config items are needed.

Populate the `provider` key in the config `auth` section with your choice. Also add any specific config required for the provider.

### Database
The database provider is used to maintain alert state, a minimise loss of alerts in the event of a bot restart.

Choices are MySQL or AWS SimpleDB. 
- MySQL : You'll need a server IP, username and password that you'd like to use. If you don't have a SQL server handy, Vagrant has setup a local SQL server that you can use. 
The account used needs to have access to create the securitybot database, and create/modify all tables. You could manually create the database yourself, in which case the database
account would just need the create/modify all tables permissions.

- SimpleDB : In AWS, create a specific IAM user with minimal perms (`"Action": ["sdb:*"]`), then add the keys to your dev host (the vagrant machine), under `~/.aws/credentials`. Standard AWS CLI stuff, see [this AWS guide][awscreds] if you need a hand.

Populate the `provider` key in the config `database` section with your choice. As with auth, add any specific config required for your chosen database provider.

### Chat
Chat is how we will interact with our users. The only choice right now is Slack. I've generally tried to imlement two choices for all providers, but Slack is pretty ubiquitous so should (hopefully) do for now. Will look at adding Mattermost in the future, or maybe Microsoft Teams?

You'll need a token to be able to integrate with Slack.
The best thing to do would be to [create a new Slack app][bot-user] and use that token for Securitybot. You'll need a "Classic App" for the time
being until I can update the bot to not use the RTM API, so use [this link][create-classic-app] to create your app. Give the app a name, like `Security Bot`
and point it at your Slack workspace. Under "App Home" add a legacy bot user, giving your bot a name, like "CyberBot".
Then, under the "OAuth and Permissions" menu, add some a Bot Token Scopes to give your bot some permissions. This is not quite least privilege, but
better than nothing for the time being. Add the following scope:

- bot

Then, head to the top of the page and install your app to your workspace. Verify the perms look good, and then hit "Allow". Almost done!
You'll now have a "Bot User OAuth Access Token" that you can configure in `config/bot.yaml` under `token` in the Slack section. 
You'll also want to set up a channel to which the bot will report when users specify that they haven't performed an action.
Find the unique ID for that channel (it'll look similar to `C123456`), and pop that in `config/bot.yaml` too, as the `reporting_channel` key.

### Secrets Management
Friends don't let friends store clear-text passwords in code! The SM provider stores your secrets/passwords secrely. The secrets are loaded from the backend
using the structure of the secrets stanza in the config, and mapped into the rest of the config at run time. Secrets are not written to disk, but are in memory for the life of the 
Security Bot instance.

Choices for secrets management are Hashicorp Vault or AWS Secrets Manager.

- Secrets Manager : In AWS, create a specific IAM user with minimal perms (permission group "SecretsManagerReadWrite"
is all that is needed) and load the creds into your dev environment. See [this AWS guide][awscreds] if you need a hand. If you decided to use SimpleDB for your 
database and followed the setup above, you just need to add the permission group to the IAM user you created/configured there. No provider specific config items are needed
for Secrets Manager. 

- Vault : You'll need your Vault URL, and a token in an environment variable of your Vagrant instance, populating the values in the relevant config section. If you don't have a Vault test server handy you can spin up a local dev instance (in Docker) on your vagrant box using the helpful helping helper script, and using `'VAULT_TOKEN_ID'` for the `token_env` and `'http://127.0.0.1:8200'` for the `url`.
```
cd /vagrant/vault
source run.sh
```
Populate the `provider` key in the config `secretsmgmt` section with your choice. Now, initialise your secrets.
```
cd /vagrant/
python3 -m securitybot.utils.initSecrets
```
You'll be prompted for any passwords and other secrets required for your chosen providers.Then, finally, you can run your bot!
```
cd /vagrant/
python3 main.py
```
When done, you can ditch your vagrant dev box.
```
vagrant destroy
```

### Running the bot
Take a look at the provided `main.py` in the root directory for an example on how to use all of these.
If the following were all generated successfully, Securitybot should be up and running.
To test it, message the bot user it's assigned to and say `hi`.
To test the process of dealing with an alert, message `test` to test the bot.

## Architecture
Securitybot was designed to be as modular as possible.
This means that it's possible to easily swap out secrets managers, databases. chat systems, 2FA providers, and alerting data sources.
Having a database allows alerts to be persistent and means that the bot doesn't lose (too much) state if there's some transient failure.

### Securitybot proper
The bot itself performs a small set of functions:

1. Reads messages, interpreting them as commands.
1. Polls each user object to update their state of applicable.
1. Grabs new alerts from the database and assigns them to users or escalates on an unknown user.

Messaging, 2FA, and alert management are provided by configurable modules, and added to the bot upon initialization.

#### Commands
The bot handles incoming messages as commands.
Command parsing and handling is done in the `Securitybot` class and the commands themselves are provided in two places.
The functions for the commands are defined in `commands.py` and their structure is defined in `commands.yaml` under the `config/` directory.

### Blacklists
Blacklists are handled by the SQL database, provided in `blacklist/blacklist.py`.

### Users
The `User` object provides support for handling user state.
We keep track of whatever information a messaging system gives to us, but really only ever use a user's unique ID and username in order to contact them.

### Alerts
Alerts are uniquely identified by a SHA-256 hash which comes from some hash of the event that generated them.

## FAQ
No I will not add support for your chat/auth/database! You are free to add yourself and contribute back to the community though!

## Contributing
Contributors must abide by the [Dropbox Contributor License Agreement][cla].

## License
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.



[slack-blog]: https://slack.engineering/distributed-security-alerting-c89414c992d6 "Distributed Alerting"
[bot-user]: https://api.slack.com/authentication/basics "Slack Bot Users"
[create-classic-app]: https://api.slack.com/apps?new_classic_app=1 "this link"
[auth-api]: https://duo.com/docs/authapi "Duo Auth API"
[cla]: https://opensource.dropbox.com/cla/ "Dropbox CLA"
[algolia]: https://github.com/algolia/securitybot "algolia"
[db-orig]: https://github.com/dropbox/securitybot "Dropbox Security Bot" 
[mew1033]: https://github.com/mew1033/securitybot "mew1033"
[awscreds]: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html "AWS Credential Files"
