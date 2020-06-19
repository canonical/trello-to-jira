#!/usr/bin/python3
import sys
import os
import json
import getpass
from optparse import OptionParser
from trello import TrelloClient

from trello_api import trello_api
from jira import JIRA
from jira_api import jira_api


# All the board current have access to
the_boards = {}
the_board_lanes = {}
the_board_members = {}
the_board_cards = []

skipped_cards       = 0
converterd_cards    = 0
failed_conversion   = 0

# Lot of Hardcoding for now
# The Goal is to get all the cards from Trello Board A and import then into JIRA Project J

# src_trello_board = "Foundations Backlog"
src_trello_board = "THE Board"
dest_jira_project= "FS"


# In our current model Lanes will become components
# The dictionnary below maps substring of current Trello lane to component into JIRA
lanes_to_components = { "General Distro":"Distro",
                        "Netplan":"netplan",
                        "Subiquity":"subiquity",
                        "Infrastructure":"Infrastructure",
                        "UC20":"Ubuntu Core",
                        "OpenJDK":"OpenJDK",
                        "Rasp":"Raspberry Pi",
                        "IBM":"IBM",
                        "Secure":"Secure Boot",
                        "Ubuntu Image":"Ubuntu Image",
                        "System":"systemd"}
 
labels_to_versions = [  "20.04",
                        "20.04.1",
                        "20.04.2",
                        "20.10",
                        "21.04"
                        ]

# What Label need to be cleaned up before importing
labels_cleanup = [  "General Distro",
                    "Subiquity",
                    "netplan",
                    "Action Item",
                    "Infrastructure",
                    "Epic",
                    "raspi",
                    "Alpha Squad",
                    "Beta Squad"]

#Initialize Trello API Token
trello = trello_api()
jira = jira_api()

#TODO Catch error opening Trello here
trello_client = TrelloClient(api_key=trello.key,token=trello.token)
jira_client = JIRA(jira.server,basic_auth=(jira.login,jira.token))


def remove_and_add(search_str,in_list,target_list,new_str=""):
    if search_str in in_list:
        in_list.pop(in_list.index(search_str))
        if new_str:
            target_list.append(new_str)
        else:
            target_list.append(search_str)
 
def handle_checklist(card):
    clists = card.checklists
    # There could be multiple checklist or no checklist
    if clists:
        for clist in clists:
            # print(clist.name)
            for item in clist.items:
                # Looks like this item is not done yet
                if not item['checked']:
                    print(" * {}".format(item['name']))

def convert_to_jira(card):
    global skipped_cards, converterd_cards, failed_conversion

    print("Converting {}".format(card.name))

    if "- 8< -" in card.name:
        print("Skipping... cut line card")
        skipped_cards+=1
        return

    jira_item_id = card.short_url

    card_labels = []
    if card.labels:
        for label in card.labels:
            card_labels.append(label.name)
    
    jira_item_name = card.name
    jira_item_description = card.description

    jira_item_type = "Task"
    if "Roadmap Item" in card_labels:
        jira_item_type = "Epic"

    # Figure out version based labels and remove label
    jira_item_components = []
    for key in lanes_to_components:
        if key in the_board_lanes[card.list_id]:
            jira_item_components.append({"name":lanes_to_components[key]})        


    # Figure out version based labels and remove label
    jira_item_versions = []
    for version in labels_to_versions:
        if version in card_labels:
            card_labels.remove(version)
            jira_item_versions.append({"name":version})

    # Label Clean up
    for label in labels_cleanup:
        if label in card_labels:
            card_labels.remove(label)

    card_labels = [x.replace(' ','') for x in card_labels]

    # TODO implement verbose mode and print the text below
    # print("Card Summary : {}".format(card.name))
    # print("Description : {}".format(card.description))
    # print("Card Type : {}".format(jira_item_type))
    # print("Assignee : ")
    # print("Reporter : ")
    # print("Components : {}".format(jira_item_components))
    # print("Fix in version : {}".format(jira_item_versions))
    # print("Labels : {}".format(card_labels))
    


    # JIRA Magic Here 
    # Test if the card has already been imported in the past
    # TODO Search could fail
    already_imported = jira_client.search_issues(
        "project = \"{}\" AND trello_card = \"{}\"".format(dest_jira_project,jira_item_id))

    if already_imported:
        print("Item {}: already imported, Skipping")
        skipped_cards += 1
    else:
        new_issue = None
        issue_dict = {
            'project': dest_jira_project,
            'summary': jira_item_name,
            'description': jira_item_description
        }
        
        if jira_item_type == "Task":
            issue_dict['issuetype'] = {'name': 'Task'}
        else:
            issue_dict['issuetype'] = {'name': 'Epic'}
            issue_dict['customfield_10011'] = jira_item_name

        # Creating custom field (trello_card) to avoid re-importing)
        issue_dict['customfield_10031'] = jira_item_id
        # importing components
        issue_dict["components"] = jira_item_components
        #importing versions
        issue_dict["fixVersions"] = jira_item_versions
        #importing labels
        issue_dict["labels"] = card_labels

        # try:
        new_issue = jira_client.create_issue(fields=issue_dict)

        # importing attachments
        attachments = card.attachments 
        if attachments:
            for url in attachments:
                link = {'url':url['url'],'title':url['name']}
                jira_client.add_simple_link(new_issue,object=link)

        # importing comments            
        comments = card.comments
        # There could be multiple comments or no comments
        if comments:
            for comment in comments:
                jira_client.add_comment(new_issue,"{} on {} :\n{}".format(
                    comment['memberCreator']['fullName'],
                    comment['date'][:10],
                    comment['data']['text']))
        
        # Creating subtasks if needed
        clists = card.checklists
        # There could be multiple checklist or no checklist
        if clists:
            # Only deal with with first checlist (majority of our cards)
            children=[]
            for item in clists[0].items:
                # Looks like this item is not done yet
                if not item['checked']:
                    subissue_dict = {
                        'project': dest_jira_project,
                        'summary': item['name'],
                        'issuetype': {'name':'Sub-task'},
                        'parent' : {'key':new_issue.key},
                        'customfield_10031' : jira_item_id,
                        'components' : jira_item_components,
                        'fixVersions' : jira_item_versions,
                        'labels' : card_labels
                    }
                    children.append(subissue_dict)

            if children:
                jira_client.create_issues(field_list=children)



        print("Created {}/browse/{}".format(jira.server,new_issue.key))
        converterd_cards += 1
        # except:
        #     print("Error converting card: {}".format(jira_item_id))
        #     failed_conversion += 1

    print("")


# Get the list of boards available to current user
for board in trello_client.list_boards():
    the_boards[board.name] = board.id

# The board we care about
# TODO: Check something went wrong
the_board = trello_client.get_board(the_boards[src_trello_board])

# Capture the board members in a dictionary
for member in the_board.get_members():
    the_board_members[member.full_name] = member.id

# Pick The Board Open Lanes
for lane in the_board.get_lists('open'):
    the_board_lanes[lane.id] = lane.name

# Capture all the cards from active lane into a dictionary
for card in the_board.open_cards():
    if card.list_id in the_board_lanes.keys():
        the_board_cards.append(card)

print ("Found {} Cards to convert to {} JIRA Project".format(len(the_board_cards),dest_jira_project))

# for card in the_board_cards:
#     convert_to_jira(card)

convert_to_jira(the_board_cards[6])

print("Convertion Report:")
print("\t{} Cards Skipped".format(skipped_cards))
print("\t{} Cards Converted".format(converterd_cards))
print("\t{} Failed Conversion".format(failed_conversion))




