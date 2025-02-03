# BeyondTrust PRA SCIM - Azure Connector
Python script that does the SCIM integration between Azure and BeyondTrust PRA.

## What is SCIM provisioning used for ?
SCIM (System for Cross-domain Identity Management) provisioning is used to streamline and standardize the way user identities and their associated attributes are managed across various systems and applications.  

By leveraging SCIM, organizations can automate the creation, updating, and removal of user accounts in multiple services simultaneously.  

This reduces manual administrative tasks, minimizes errors, and ensures that access and identity information are kept consistent and up-to-date across all integrated platforms.  

Additionally, by performing provisioning prior to the user's initial login, it ensures the user is already created and manageable in the system before they access the application for the first time.

## What is this script ?
As you may know, and if you have BeyondTrust Privileged Remote Access (PRA) in your company, you may have already tried the SCIM integration between Microsoft Azure and PRA.  

The result obtained on the Microsoft side is not the expected one, since our integration throws an error at each request and requests a new integration with each change of rights on the application.  

This error is due to a bad integration of the [SCIM API](https://scim.cloud/) within PRA. It was not developed properly, and does not allow all the features that Microsoft, Google and other IDPs will use to provision accounts and groups.  

So this script was made to replace the existing functionality of Microsoft Azure by using the application itself, and the features present on the PRA API.

## Needed rights to make the script to work
### On Microsoft Azure :

Make sure to give these rights to the same application you use for SAML Authentication.

- Microsoft Graph :
  - Application permissions :
    - Directory.Read.All
    - Directory.ReadWrite.All
    - Group.Read.All
    - User.Read.All

### On BeyondTrust PRA :
- SCIM API
  - Allow Access
  - Allow long-lived bearer token

## How do I start the code ?

Once you have cloned the repo, you will need to install the dependencies with the following command :
```bash
py -3 -m pip install -r requirements.txt # Windows
python3 -m pip install -r requirements.txt # Linux
```

And edit the file between the lines 13 and 20 :
```py
tenant_id = ""
client_id = ""
client_secret = ""
    
url = ""
PRAclientSecret = ""
```
  

An example of the values you can enter is like this one :
```py
tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
client_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
client_secret = "some-random-password-value"
    
url = "https://pra.example.com" # Do not put the / after the TLD
PRAclientSecret = "some-random-api-key"
```

Once done, you can put the file as a scheduled task on one of your servers to run every day, every hour or whenever you want.  

## Does it works for Remote Support (RS) ?
I haven't tested the script on RS, however it is possible that this script will work as well.

## Need Help or Have Questions ?
If you encounter any issues, feel free to open an issue on this repository.
For further assistance or inquiries, you can reach me at [contact@unbonwhisky.fr](mailto:contact@unbonwhisky.fr)
