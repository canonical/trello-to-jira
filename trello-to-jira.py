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

# The Goal is to get all the cards from Trello Board A and import then into JIRA Project J

src_trello_board = ""
# JIRA project key
dest_jira_project= ""

# This Label means this is an Epic
# epic_label = "`Roadmap` Item"
# epic_name_field = 'customfield_10011'
# epic_parent_filed = 'customfield_10014'
bug_label = "Bug"

# If your  current model has Lanes for components
# The dictionnary below maps substring of current Trello lane to component into JIRA
# Components need to exist in JIRA
lanes_to_components = { "Trello Lane":"JIRA Component"}

# If your  current model has Lanes for status
# The dictionnary below maps substring of current Trello lane to status into JIRA
# Status needs to exist in your JIRA project
# [('11', 'Backlog'),
#  ('21', 'Selected for Development'),
#  ('31', 'In Progress'),
#  ('41', 'Done'),
#  ('51', 'REVIEW'),
#  ('61', 'BLOCKED')]

lanes_to_status = { "Prioritized Queue":'21',
                    "Committed":'21',
                    "In Progress" : '31',
                    "Needs Review":'51',
                    "Blocked":'61'}

# JIRA Account ID mapping allowing to map trello user to Jira user
jira_member_id = { "John Doe":"5d39ea58c395b60ca64748c4"}

# If your  current model has Labels set for components
# The dictionnary below will maps Trello labels to components into JIRA
# Components need to exist in JIRA
labels_to_components = { "Trello Label":"JIRA Component"}

# What versions in Trello as label need to be mapped to actual versions
# Versions need to exists in the Target JIRA project
labels_to_versions = [  "18.04",
                        "20.04",
                        "20.04.1",
                        "20.04.2",
                        "20.10",
                        "21.04"
                        ]

# What Trello Labels need to be cleaned up before importing

labels_cleanup = ["Label to be removed"]

def convert_to_jira(card, dryrun = False):
    global skipped_cards, converterd_cards, failed_conversion

    # print("Converting {}".format(card.name))

    if "- 8< -" in card.name:
        # print("Skipping... cut line card")
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
    if bug_label in card_labels:
        jira_item_type = "Bug"
        card_labels.remove(bug_label)

    # Figure out status based on the lane
    jira_item_status = None
    if lanes_to_status:
        for key in lanes_to_status:
            if key in the_board_lanes[card.list_id]:
                jira_item_status = lanes_to_status[key]

    # Figure out component based on lane 
    jira_item_components = []
    if lanes_to_components:
        for key in lanes_to_components:
            if key in the_board_lanes[card.list_id]:
                jira_item_components.append({"name":lanes_to_components[key]})

    # Figure out component based on label and remove label
    if labels_to_components:
        for component in labels_to_components:
            if component in card_labels:
                card_labels.remove(component)
                jira_item_components.append({"name":labels_to_components[component]})

    # Figure out version based labels and remove label
    jira_item_versions = []
    if labels_to_versions:
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

    # Handle Who is assigned to the Card
    accountID = None

    # Convert current Trello owner to future JIRA assignee ID
    if card.member_id:
        username = list(the_board_members.keys())[list(the_board_members.values()).index(card.member_id[0])]
        if username in jira_member_id.keys():
            accountID = jira_member_id[username]

    # JIRA Magic Here 
    # Test if the card has already been imported in the past
    # TODO Search could fail
    already_imported = jira_client.search_issues(
        "project = \"{}\" AND trello_card = \"{}\"".format(dest_jira_project,jira_item_id))

    if already_imported:
        print("[Skipped] - {}: already imported, Skipping".format(jira_item_id),flush = True)
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
            issue_dict['issuetype'] = {'name': 'Bug'}
        #     issue_dict['customfield_10011'] = jira_item_name

        # Creating custom field (trello_card) to avoid re-importing)
        issue_dict['customfield_10031'] = jira_item_id
        # importing components
        issue_dict["components"] = jira_item_components
        #importing versions
        issue_dict["fixVersions"] = jira_item_versions
        #importing labels
        issue_dict["labels"] = card_labels

        #Assignee
        if accountID:
            issue_dict['assignee'] = {'accountId': accountID}

        try:
            new_issue = None

            if not dryrun:
                new_issue = jira_client.create_issue(fields=issue_dict)

            # importing attachments
            attachments = card.attachments
            if attachments:
                for url in attachments:
                    link = {'url':url['url'],'title':url['name']}
                    if not dryrun:
                        jira_client.add_simple_link(new_issue,object=link)

            # importing comments
            comments = card.comments
            # There could be multiple comments or no comments
            if comments:
                for comment in comments:
                    if not dryrun:
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
                            'customfield_10031' : jira_item_id,
                            'components' : jira_item_components,
                            'fixVersions' : jira_item_versions,
                            'labels' : card_labels
                        }
                        # if jira_item_type == "Epic":
                        #     subissue_dict['issuetype'] = {'name':'Task'}
                        #     subissue_dict['customfield_10014'] = new_issue.key
                        # else:
                        subissue_dict['issuetype'] = {'name': 'Sub-task'}
                        if not dryrun:
                            subissue_dict['parent'] = {'key':new_issue.key}

                        children.append(subissue_dict)

                if children:
                    if not dryrun:
                        jira_client.create_issues(field_list=children)

            # Transition issue if needed
            if jira_item_status:
                if not dryrun:
                    jira_client.transition_issue(new_issue,jira_item_status)
            if not dryrun:
                # Leaving a note in Trello
                card.comment("Card tracking moved to {}/browse/{}".format(jira.server,new_issue.key))
                print("[Converted] - {} -> {}/browse/{}".format(jira_item_id,jira.server,new_issue.key),flush = True)
            else:
                print("[Converted] - {} -> {}/browse/TBD".format(jira_item_id,jira.server),flush = True)

            converterd_cards += 1

        except:
            print("[Error] - {}".format(jira_item_id),flush = True)
            failed_conversion += 1


# TODO: would be better with arguments parsing than chaning those values in the code
if not src_trello_board or not dest_jira_project:
    print("src_trello_board and dest_jira_project are not set")
    sys.exit(1)

#Initialize Trello API Token
trello = trello_api()
jira = jira_api()

#TODO Catch error opening Trello here
trello_client = TrelloClient(api_key=trello.key,token=trello.token)
jira_client = JIRA(jira.server,basic_auth=(jira.login,jira.token))



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

index = 0
for card in the_board_cards:
    print("{} - ".format(index),flush=True,end='')
    convert_to_jira(card)
    index += 1


print("Convertion Report:")
print("\t{} Cards Skipped".format(skipped_cards))
print("\t{} Cards Converted".format(converterd_cards))
print("\t{} Failed Conversion".format(failed_conversion))




