Trello to JIRA

Custom Trello to JIRA importer that import the content of a Board into a JIRA project
This is very custom at this time and would need to get some level of abstraction to become public

Assumption at this time are that:
* Labels include versions and corresponding versions should be in the JIRA project
* in this example Lanes represents Components and can be mapped to existing components in JIRA
* TODO: It sould be fairly easy to map Label based components to components as well

Support conversion at this time:
Trello Attributes   to      JIRA Attributes     
    Title           >>      Title               
    Description     >>      Description         
    Labels          >>      Versions            
    Labels          >>      Labels              
    Labels          >>      Type (Epic/Task)    
    Lane            >>      Components          
    Link            >>      Link
    Checklist       >>      sub tasks
      * the importer will turn the first checklist into sub tasks
    Comments        >>      Comments 
      * All comments will be from the importer but will include the original commentor and timestamp
