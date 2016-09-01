import logging
from itertools import chain

from errbot import BotPlugin, botcmd

log = logging.getLogger(name='errbot.plugins.Jira')

CONFIG_TEMPLATE = {
    'API_URL': 'http://jira.example.com',
    'USERNAME': 'errbot',
    'PASSWORD': 'password',
    'OAUTH_ACCESS_TOKEN': None,
    'OAUTH_ACCESS_TOKEN_SECRET': None,
    'OAUTH_CONSUMER_KEY': None,
    'OAUTH_KEY_CERT_FILE': None,
}

try:
    from jira import JIRA, JIRAError
except ImportError:
    log.error("Please install 'jira' python package")


class Jira(BotPlugin):
    """An errbot plugin for working with Atlassian JIRA"""

    def activate(self):

        if not self.config:
            #Don't allow activation until we are configured
            message = 'Jira is not configured, please do so.'
            self.log.info(message)
            self.warn_admins(message)
            return

        self.jira_connect = self._login()
        if self.jira_connect:
            super().activate()

    def configure(self, configuration):
        if configuration is not None and configuration != {}:
            config = dict(
                chain(
                    CONFIG_TEMPLATE.items(),
                    configuration.items(),
                )
            )
        else:
            config = CONFIG_TEMPLATE
        super(Jira, self).configure(config)

    def get_configuration_template(self):
        """Returns a template of the configuration this plugin supports"""
        return CONFIG_TEMPLATE

    def check_configuration(self, configuration):
        # TODO: do some validation here!
        pass

    def _check_ticket_passed(self, msg, ticket):

        if ticket == '':
            self.send(msg.frm,
                      'Ticket must be passed',
                      message_type=msg.type,
                      in_reply_to=msg,
                      groupchat_nick_reply=True)
            return False

        return True

    def _login(self):
        self.jira_connect = None
        self.jira_connect = self._login_oauth()
        if self.jira_connect:
            return self.jira_connect
        self.jira_connect = None
        self.jira_connect = self._login_basic()
        if self.jira_connect:
            return self.jira_connect
        return None

    def _login_oauth(self):
        API_URL = self.config['API_URL']
        # TODO: make this check more robust
        if self.config['OAUTH_ACCESS_TOKEN'] is None:
            message = 'oauth configuration not set'
            self.log.info(message)
            return False

        key_cert_data = None
        cert_file = self.config['OAUTH_KEY_CERT_FILE']
        try:
            with open(cert_file, 'r') as key_cert_file:
                key_cert_data = key_cert_file.read()
            oauth_dict = {
                'access_token': self.config['OAUTH_ACCESS_TOKEN'],
                'access_token_secret': self.config['OAUTH_ACCESS_TOKEN_SECRET'],
                'consumer_key': self.config['OAUTH_CONSUMER_KEY'],
                'key_cert': key_cert_data
            }
            authed_jira = JIRA(server=API_URL, oauth=oauth_dict)
            self.log.info('logging into {} via oauth'.format(API_URL))
            return authed_jira
        except JIRAError:
            message = 'Unable to login to {} via oauth'.format(API_URL)
            self.log.error(message)
            return False
        except TypeError:
            message = 'Unable to read key file {}'.format(cert_file)
            self.log.error(message)
            return False

    def _login_basic(self):
        """"""
        api_url = self.config['API_URL']
        username = self.config['USERNAME']
        password = self.config['PASSWORD']
        try:
            authed_jira = JIRA(server=api_url, basic_auth=(username, password))
            self.log.info('logging into {} via basic auth'.format(api_url))
            return authed_jira
        except JIRAError:
            message = 'Unable to login to {} via basic auth'.format(api_url)
            self.log.error(message)
            return False

    @botcmd(split_args_with=' ')
    def jira(self, msg, args):
        """
        Returns the subject of the ticket along with a link to it.
        """

        ticket = args.pop(0).upper()
        if not self._check_ticket_passed(msg, ticket):
            return

        jira = self.jira_connect

        try:
            issue = jira.issue(ticket)

            response = '{0} created on {1} by {2} ({4}) - {3}'.format(
                issue.fields.summary,
                issue.fields.created,
                issue.fields.reporter.displayName,
                issue.permalink(),
                issue.fields.status.name
            )
        except JIRAError:
            response = 'Ticket {0} not found.'.format(ticket)

        self.send(msg.frm,
                  response,
                  message_type=msg.type,
                  in_reply_to=msg,
                  groupchat_nick_reply=True)

    @botcmd(split_args_with=' ')
    def jira_comment(self, msg, args):
        """
        Adds a comment to a ticket
        Options:
            ticket: jira ticket
            comment: text to add to ticket
        Example
        !jira comment PROJECT-123 I need to revisit this.
        """

        ticket = args.pop(0).upper()
        raw_comment = ' '.join(args)

        if not self._check_ticket_passed(msg, ticket):
            return

        jira = self.jira_connect

        try:
            issue = jira.issue(ticket)
            user = msg.frm
            comment = '{} added: {}'.format(user, raw_comment)
            jira.add_comment(issue, comment)
            response = 'Added comment to {}'.format(ticket)
        except JIRAError:
            response = 'Unable to add comment to {0}.'.format(ticket)

        self.send(msg.frm,
                  response,
                  message_type=msg.type,
                  in_reply_to=msg,
                  groupchat_nick_reply=True)

    @botcmd(split_args_with=' ')
    def jira_reassign(self, msg, args):
        """
        Reassign a ticket to someone else
        Options:
            ticket: jira ticket
            user: user to reassign ticket
        Example
        !jira reassign PROJECT-123 sijis
        """

        ticket = args.pop(0).upper()
        user = args.pop(0)

        if not self._check_ticket_passed(msg, ticket):
            return

        jira = self.jira_connect

        try:
            issue = jira.issue(ticket)
            issue.update(fields={'assignee': {'name':user}})
            response = 'Reassigned {} to {}'.format(ticket, user)
        except JIRAError:
            response = 'Unable to reassign {} to {}'.format(ticket, user)

        self.send(msg.frm,
                  response,
                  message_type=msg.type,
                  in_reply_to=msg,
                  groupchat_nick_reply=True)
