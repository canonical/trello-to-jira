import json
import os

class trello_api():

    def __init__(self,credentials="{}/.trello.creds".format(os.path.expanduser('~'))):

        self.credstore = credentials
        
        try:
            with open(self.credstore) as f:
                config = json.load(f)
                self.key = config['api_key']
                self.token = config['token']
        
        except (FileNotFoundError, json.JSONDecodeError):
            print('Trello Token information file {} could not be found or parsed.'.format(self.credstore))
            print('')
            gather_token = input('Do you want to enter your Trello token information now (see https://trello.com/app-key/) ? (Y/n) ')
            if gather_token == 'n':
                return 1
            self.key = input('Please enter your Trello api key : ')
            self.token = input('Please enter your Trello api token : ')
            save_token = input('Do you want to save those credentials for future use of trello-to-jira? (Y/n) ')
            if save_token != 'n':
                try:
                    data = {}
                    data['api_key'] = self.key
                    data['token'] = self.token
                    with open(self.credstore,'w+') as f:
                        json.dump(data,(f))
                except (FileNotFoundError, json.JSONDecodeError):
                    # TODO: Probably better error handling can be done here
                    print("Something went wrong saving credentials")
                    return 1

