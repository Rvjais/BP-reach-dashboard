HeyReach API
Introduction
Welcome to the HeyReach API. Let' get started with a quick setup on how to use the API!

Finding your API key
The first step when using the HeyReach API is authenticating your requests with an API key.
The API key is used to authenticate the incoming requests and map them to your organization.
API keys never expire, however they can be deleted/deactivated.

Authentication
After you have your API key, you will need to provide it in every request that you make to the HeyReach API.
You will need to use add the X-API-KEY request header to every request and set you API key as the value.

Test your API key
Once you have your API key, you can check if it's working by sending the following request.
If everything is working properly, you should get a 200 HTTP status code.

Plain Text
curl --location &#x27;https://api.heyreach.io/api/public/auth/CheckApiKey&#x27; --header &#x27;X-API-KEY: <YOUR_API_KEY>&#x27;
Rate Limits
HeyReach allows a maximum of 300 requests per minute. All requests are attributed to the same limit.
Going above the limit will return a 429 HTTP status code and an error.

Enjoy building 🛠️
PATCH
Update Webhook
https://api.heyreach.io/api/public/webhooks/UpdateWebhook?webhookId=1234
Update Webhook
Endpoint
PATCH https://api.heyreach.io/api/public/webhooks/UpdateWebhook?webhookId=1234

Description
This API updates an existing webhook by modifying its configuration, such as name, URL, event type, associated campaigns, and status.

Query Parameters
webhookId (string): The unique identifier of the webhook to update. This must be provided as a query parameter.
Request Body Example
json
{
  "webhookName": "string",
  "webhookUrl": "string",
  "eventType": "CONNECTION_REQUEST_SENT",
  "campaignIds": [],
  "isActive": true
}
Request Parameters
webhookName (string): The name of the webhook. If NULL or ommited, the original name will be kept.

webhookUrl (string): The URL to which the webhook will send POST requests. If NULL or ommited, the orignal url will be kept

eventType (string): The type of event that triggers the webhook. If null or ommited, the original will be kept.
It must be one of the following values:

CONNECTION_REQUEST_SENT

CONNECTION_REQUEST_ACCEPTED

MESSAGE_SENT

MESSAGE_REPLY_RECEIVED

INMAIL_SENT

INMAIL_REPLY_RECEIVED

FOLLOW_SENT

LIKED_POST

VIEWED_PROFILE

CAMPAIGN_COMPLETED

LEAD_TAG_UPDATED

campaignIds (array): A list of campaign IDs.
If null or ommited, the original array will be kept.
If this array is empty, the webhook will listen for the specified eventType across all campaigns. If specific campaign IDs are provided, the webhook will listen only to those campaigns.

isActive (boolean | null): Determines whether the webhook should be active. If true, the webhook is enabled; if false, it is disabled. If null, the activation status remains unchanged.

HEADERS
X-API-KEY
<string>

API key header using this scheme. Example: "X-API-KEY: {API_KEY}"

Content-Type
application/json

Accept
text/plain

PARAMS
webhookId
1234

Body
raw (json)
View More
json
{
  "webhookName": "string" | null,
  "webhookUrl": "string" | null,
  "eventType": "CONNECTION_REQUEST_SENT" | "CONNECTION_REQUEST_ACCEPTED" | "MESSAGE_SENT" | "MESSAGE_REPLY_RECEIVED" | "INMAIL_SENT" | "INMAIL_REPLY_RECEIVED" | "FOLLOW_SENT" | "LIKED_POST" | "VIEWED_PROFILE" | "CAMPAIGN_COMPLETED" | "LEAD_TAG_UPDATED" | null
  "campaignIds": [] | null
  "isActive": true | null
}
Example Request
Update Webhook
View More
curl
curl --location --request PATCH 'https://api.heyreach.io/api/public/webhooks/UpdateWebhook?webhookId=1234' \
--header 'X-API-KEY: <string>' \
--header 'Content-Type: application/json' \
--header 'Accept: text/plain' \
--data '{
  "webhookName": "string" | null,
  "webhookUrl": "string" | null,
  "eventType": "CONNECTION_REQUEST_SENT" | "CONNECTION_REQUEST_ACCEPTED" | "MESSAGE_SENT" | "MESSAGE_REPLY_RECEIVED" | "INMAIL_SENT" | "INMAIL_REPLY_RECEIVED" | "FOLLOW_SENT" | "LIKED_POST" | "VIEWED_PROFILE" | "CAMPAIGN_COMPLETED" | "LEAD_TAG_UPDATED" | null
  "campaignIds": [] | null
  "isActive": true | null
}'
Example Response
Body
Headers (0)
No response body
This request doesn't return any response body
POST
InviteManagers
https://api.heyreach.io/api/public/management/organizations/users/invite/managers
Invite one or multiple users as managers in your organization. Manager users are special kind of users that exist outside your organization and are invited to specific workspaces. These users will not be part of you organization and only have access to the specified workspaces. These users are automatically added to your workspace and don't need to register.

HEADERS
X-API-KEY
Workspace API Key

Content-Type
application/json

Accept
text/plain

Body
raw (json)
json
{
  "inviterEmail": "nzLa4CYTiLt@yXST.ltrp",
  "emails": [
    "string",
    "string"
  ],
  "workspaceIds": [
    6519,
    3651
  ]
}
Example Request
Success
View More
curl
curl --location 'https://api.heyreach.io/api/public/management/organizations/users/invite/managers' \
--header 'X-API-KEY;' \
--header 'Content-Type: application/json' \
--header 'Accept: text/plain' \
--data-raw '{
  "inviterEmail": "nzLa4CYTiLt@yXST.ltrp",
  "emails": [
    "string",
    "string"
  ],
  "workspaceIds": [
    6519,
    3651
  ]
}'
200 OK
Example Response
Body
Headers (1)
View More
json
[
  {
    "workspaces": [
      {
        "workspaceId": 5937,
        "success": true,
        "errorCode": "Success",
        "errorMessage": "string"
      },
      {
        "workspaceId": 2957,
        "success": true,
        "errorCode": "UnknownError",
        "errorMessage": "string"
      }
    ],
    "invitationId": 7510,
    "invitationStatus": "Pending",
    "invitationUrl": "string",
    "invitationExpirationTime": "2011-12-31T22:55:45.978Z",
    "emailAddress": "string"
  },
  {
    "workspaces": [
      {
        "workspaceId": 9214,
        "success": true,
        "errorCode": "UnknownError",
        "errorMessage": "string"
      },
      {
        "workspaceId": 1177,
        "success": false,
        "errorCode": "WorkspaceDoesNotExists",
        "errorMessage": "string"
      }
    ],
    "invitationId": 8662,
    "invitationStatus": "Revoked",
    "invitationUrl": "string",
    "invitationExpirationTime": "1947-11-19T13:31:07.591Z",
    "emailAddress": "string"
  }
]
GET
GetUserById
https://api.heyreach.io/api/public/management/organizations/users/:userId
Get information about a given user.

HEADERS
X-API-KEY
Workspace API Key

Accept
text/plain

PATH VARIABLES
userId
5421

Example Request
Success
curl
curl --location 'https://api.heyreach.io/api/public/management/organizations/users/5421' \
--header 'X-API-KEY;' \
--header 'Accept: text/plain'
200 OK
Example Response
Body
Headers (1)
View More
json
{
  "userDetails": {
    "userId": 1846,
    "name": "string",
    "surname": "string",
    "email": "string",
    "roles": [
      "string",
      "string"
    ]
  },
  "organizationPermissions": {
    "userDeactivate": false,
    "manageWorkspace": false,
    "manageWorkspaceMembers": false,
    "viewBilling": false,
    "manageBlling": false,
    "manageBillingDetails": false,
    "accessBillingInvoiceHistoy": false
  },
  "workspacesPermissions": [
    {
      "workspaceName": "string",
      "workspaceId": 8053,
      "permissions": {
        "viewLinkedInSenders": false,
        "manageLinkedInSendersSettings": false,
        "viewLeadLists": false,
        "importEditManageLeadLists": false,
        "viewMyNetwork": false,
        "viewCampaigns": false,
        "editManageCampaigns": false,
        "viewLinkedInSenderInboxes": false,
        "replyFromLinkedInSenderInboxes": false,
        "viewIntegrations": false,
        "manageIntegrations": false,
        "exportDataToCRMs": false,
        "viewNotifications": false,
        "manageNotifications": false
      }
    },
    {
      "workspaceName": "string",
      "workspaceId": 781,
      "permissions": {
        "viewLinkedInSenders": false,
        "manageLinkedInSendersSettings": false,
        "viewLeadLists": false,
        "importEditManageLeadLists": false,
        "viewMyNetwork": false,
        "viewCampaigns": false,
        "editManageCampaigns": false,
        "viewLinkedInSenderInboxes": false,
        "replyFromLinkedInSenderInboxes": false,
        "viewIntegrations": false,
        "manageIntegrations": false,
        "exportDataToCRMs": false,
        "viewNotifications": false,
        "manageNotifications": false
      }
    }
  ]
}
POST
GetWorkspaceUsers
https://api.heyreach.io/api/public/management/organizations/users/workspaces/:workspaceId
Get all users in a given workspace along with their role and permissions.

HEADERS
X-API-KEY
Workspace API Key

Content-Type
application/json

Accept
text/plain

PATH VARIABLES
workspaceId
5421

Body
raw (json)
json
{
  "offset": 895,
  "role": "Admin",
  "invitationStatus": [
    "Accepted",
    "Pending"
  ],
  "limit": 38
}
Example Request
Success
View More
curl
curl --location 'https://api.heyreach.io/api/public/management/organizations/users/workspaces/5421' \
--header 'X-API-KEY;' \
--header 'Content-Type: application/json' \
--header 'Accept: text/plain' \
--data '{
  "offset": 895,
  "role": "Admin",
  "invitationStatus": [
    "Accepted",
    "Pending"
  ],
  "limit": 38
}'
200 OK
Example Response
Body
Headers (1)
View More
json
{
  "totalCount": 1040,
  "items": [
    {
      "workspaceId": 9178,
      "organizationPermissions": {
        "userDeactivate": false,
        "manageWorkspace": false,
        "manageWorkspaceMembers": false,
        "viewBilling": false,
        "manageBlling": false,
        "manageBillingDetails": false,
        "accessBillingInvoiceHistoy": false
      },
      "workspacePermissions": {
        "viewLinkedInSenders": false,