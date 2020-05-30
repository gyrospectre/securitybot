# Securitybot
### Distributed alerting for the masses!
A fork of the famous [Dropbox Security Bot][db-orig], which is no longer maintained and getting a bit long in the tooth! It's been given a fresh coat of paint,
via [Antoine Cardon][algolia] who did some great work a few years ago with Python3 conversion and some extra cleanup.

Securitybot is an open-source implementation of a distributed alerting chat bot, as described in Ryan Huber's [blog post][slack-blog].
Distributed alerting improves the monitoring efficiency of your security team and can help you catch security incidents faster and more efficiently.

The ultimate goal is a seamless install running in AWS in a Lambda, with all creds in Secrets Manager, and using Slack Event subscription
rather than the old RTM API, but right now it's just a working codebase with some Vagrant lovliness to get a dev environment up and running easily.

## Deploying
This guide runs through setting up a Securitybot instance as quickly as possible with no frills.

## Quick Start
Install vagrant and virtualbox on your dev machine. Then, deploy the code into a VM:
```
git clone https://github.com/gyrospectre/securitybot.git
cd securitybot
vagrant up
```
Vagrant will spin up an Ubuntu VM, install and configure MySQL, and install python deps. Populate `config/bot.yaml` with your
Slack token and reporting_channel (see Slack section below) at a minimum, and then run your bot!
```
vagrant ssh
cd /vagrant
python3 main.py
```
When done, you can ditch your vagrant dev box.
```
vagrant destroy
```

### SQL
Ew. Ewww. Keeping SQL for the time being but this will go soon. Please, please do not deploy this to prod as is. It uses the root user, 
has a stupid password, and creds are cleartext in config files.

### Slack
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

### Duo
For Duo, you'll want to create an [Auth API][auth-api] instances, name it something clever, and keep track of the integration key, secret key, and auth API endpoint URI.
I don't use Duo, so have not tested this.

### Okta
Okta support in progress, building on [mew1033]'s initial work.
 
### Running the bot
Take a look at the provided `main.py` in the root directory for an example on how to use all of these.
If the following were all generated successfully, Securitybot should be up and running.
To test it, message the bot user it's assigned to and say `hi`.
To test the process of dealing with an alert, message `test` to test the bot.

## Architecture
Securitybot was designed to be as modular as possible.
This means that it's possible to easily swap out chat systems, 2FA providers, and alerting data sources.
The only system that is tightly integrated with the bot is SQL, but adding support for other databases shouldn't be difficult.
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

### Messaging
Securitybot is designed to be compatible with a wide variety of messaging systems.
We currently provide bindings for Slack, but feel free to contribute any other plugins, like for Gitter or Zulip, upstream.
Messaging is made possible by `securitybot/chat/chat.py` which provides a small number of functions for querying users in a messaging group, messaging those users, and sending messages to a specific channel/room.
To add bindings for a new messaging system, subclass `Chat`.

### 2FA
2FA support is provided by `auth/auth.py`, which wraps async 2FA in a few functions that enable checking for 2FA capability, starting a 2FA session, and polling the state of the 2FA session.
We provide support for Duo Push via the Duo Auth API, but adding support for a different product or some in-house 2FA solution is as easy as creating a subclass of `Auth`.

### Task management
Task management is provided by `tasker/tasker.py` and the `Tasker` class.
Since alerts are logged in an SQL database, the provided Tasker is `SQLTasker`.
This provides support for grabbing new tasks and updating them via individual `Task` objects.

### Blacklists
Blacklists are handled by the SQL database, provided in `blacklist/blacklist.py` and the subclass `blacklist/sql_blacklist.py`.

### Users
The `User` object provides support for handling user state.
We keep track of whatever information a messaging system gives to us, but really only ever use a user's unique ID and username in order to contact them.

### Alerts
Alerts are uniquely identified by a SHA-256 hash which comes from some hash of the event that generated them.
We assume that a SHA-256 hash is sufficiently random for there to be no collisions.
If you encounter a SHA-256 collision, please contact someone at your nearest University and enjoy the fame and fortune it brings upon you.

## FAQ

Please ask us things

## Contributing
Contributors must abide by the [Dropbox Contributor License Agreement][cla].

## License

Copyright 2016 Dropbox, Inc.

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
