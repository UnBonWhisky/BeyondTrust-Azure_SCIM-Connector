import asyncio
import httpx
import json

async def main():
    ################# EDIT HERE WITH YOUR INFORMATIONS #################
    # Needed rights : Microsoft Graph ->
    #   Application permissions ->
    #     "Directory.Read.All",
    #     "Directory.ReadWrite.All",
    #     "Group.Read.All",
    #     "User.Read.All"
    tenant_id = "" # Your Azure AD tenant ID
    client_id = "" # Your Azure AD application ID
    client_secret = "" # Your Azure AD application secret
    
    # URL of your PRA tenant and secret for SCIM access
    url = "" # PRA URL (ex: https://pra.example.com)
    PRAclientSecret = "" # PRA SCIM secret. Needed rights : SCIM API -> "Allow Access", "Allow long-lived bearer token"
    ########################### STOP EDITING ###########################

    Users_Url = f"{url}/api/scim/Users"
    Groups_Url = f"{url}/api/scim/Groups"

    # Scope Graph
    scope = "https://graph.microsoft.com/.default"
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get the access token (Client Credentials Flow)
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope
        }
        
        response = await client.post(token_url, data=data)
        response.raise_for_status()
        token_info = response.json()
        access_token = token_info["access_token"]

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # 1. Get the servicePrincipal corresponding to the application via the appId
        service_principal_url = f"https://graph.microsoft.com/v1.0/servicePrincipals?$filter=appId eq '{client_id}'"
        sp_response = await client.get(service_principal_url, headers=headers)
        sp_response.raise_for_status()
        service_principals = sp_response.json().get('value', [])

        if not service_principals:
            print("Aucun servicePrincipal trouvé pour cette application.")
            return

        # Supposing there is only one servicePrincipal
        service_principal_id = service_principals[0]['id']

        # 2. Get the assignments (users and groups) on the servicePrincipal
        assigned_to_url = f"https://graph.microsoft.com/v1.0/servicePrincipals/{service_principal_id}/appRoleAssignedTo"
        assigned_response = await client.get(assigned_to_url, headers=headers)
        assigned_response.raise_for_status()
        assigned_objects = assigned_response.json().get('value', [])

        if not assigned_objects:
            print("Aucun utilisateur ou groupe assigné à cette application.")
            return

        # Utility functions
        async def get_directory_object(obj_id):
            # Get the object from the directory (user or group)
            obj_url = f"https://graph.microsoft.com/v1.0/directoryObjects/{obj_id}"
            resp = await client.get(obj_url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        
        async def get_group_members(group_id):
            # Get the members of a group
            mem_url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members"
            resp = await client.get(mem_url, headers=headers)
            resp.raise_for_status()
            return resp.json().get('value', [])

        def parse_user(user_json):
            full_name = user_json.get('displayName', '')
            email = user_json.get('userPrincipalName', '')
            external_id = email.split("@")[0] if "@" in email else email
            names = full_name.split()
            firstname = names[0] if names else ''
            lastname = " ".join(names[1:]) if len(names) > 1 else ''
            return {
                "COMPLETE_NAME": full_name,
                "EMAIL": email,
                "FIRSTNAME": firstname,
                "LASTNAME": lastname,
                "EXTERNAL_ID": external_id,
                "TYPE": "User"
            }

        # Get the users and groups from the assignments
        UserData = []
        GroupData = []

        for obj in assigned_objects:
            principal_id = obj['principalId']
            principal_data = await get_directory_object(principal_id)
            object_type = principal_data.get('@odata.type', '')

            if 'user' in object_type:
                # This is a user
                user_obj = parse_user(principal_data)
                UserData.append(user_obj)
            elif 'group' in object_type:
                # This is a group
                group_obj = {
                    "ID": principal_id,
                    "NAME": principal_data.get('displayName', ''),
                    "TYPE": "Group"
                }
                GroupData.append(group_obj)

                # Get the group members
                members = await get_group_members(principal_id)
                for m in members:
                    m_type = m.get('@odata.type', '')
                    if 'user' in m_type:
                        user_obj = parse_user(m)
                        user_obj["GROUP"] = principal_id
                        UserData.append(user_obj)

        # Deduplicate UserData (based on EMAIL)
        seen_emails = set()
        unique_UserData = []
        for u in UserData:
            email = u["EMAIL"]
            if email not in seen_emails:
                seen_emails.add(email)
                unique_UserData.append(u)
        UserData = unique_UserData

        # Get the existing users and groups in PRA using SCIM
        SCIM_headers = {
            'Authorization': 'Bearer ' + PRAclientSecret,
            'Content-Type': 'application/scim+json'
        }

        async def get_pra_users():
            resp = await client.get(Users_Url, headers=SCIM_headers)
            resp.raise_for_status()
            resources = resp.json().get('Resources', [])
            return [{
                "USERNAME": r.get('displayName'),
                "EMAIL": r.get('emails', [{}])[0].get('value'),
                "ID": r.get('id')
            } for r in resources]

        async def get_pra_groups():
            resp = await client.get(Groups_Url, headers=SCIM_headers)
            resp.raise_for_status()
            resources = resp.json().get('Resources', [])
            return [{
                "NAME": r.get('displayName'),
                "ID": r.get('id'),
                "MEMBERS": [m.get('value') for m in r.get('members', [])]
            } for r in resources]

        PRAUserData = await get_pra_users()
        PRAGroupData = await get_pra_groups()

        # Add the non-existing groups in PRA
        for group in GroupData:
            if not any(pg["NAME"] == group["NAME"] for pg in PRAGroupData):
                AddDatas = {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                    "displayName": group["NAME"],
                    "externalId": group["ID"]
                }
                resp = await client.post(Groups_Url, headers=SCIM_headers, data=json.dumps(AddDatas))
                resp.raise_for_status()
                print(f"Group added to PRA : {group['NAME']}")

        # Get the updated list of groups in PRA
        PRAGroupData = await get_pra_groups()

        # Delete groups that are not in Azure AD anymore
        for praGroup in PRAGroupData:
            if not any(g["NAME"] == praGroup["NAME"] for g in GroupData):
                delete_url = f"{Groups_Url}/{praGroup['ID']}"
                resp = await client.delete(delete_url, headers=SCIM_headers)
                resp.raise_for_status()
                print(f"Group removed from PRA : {praGroup['NAME']}")

        # Get the updated list of groups in PRA
        PRAGroupData = await get_pra_groups()

        # Add missing users in PRA
        for user in UserData:
            if not any(pu["EMAIL"] == user["EMAIL"] for pu in PRAUserData):
                AddDatas = {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "userName": user["EMAIL"],
                    "displayName": user["COMPLETE_NAME"],
                    "externalId": user["EXTERNAL_ID"],
                    "Active": True,
                    "name": {
                        "formatted": user["COMPLETE_NAME"],
                        "familyName": user["LASTNAME"],
                        "givenName": user["FIRSTNAME"]
                    },
                    "emails": [
                        {
                            "value": user["EMAIL"],
                            "type": "work",
                            "primary": True
                        }
                    ]
                }
                resp = await client.post(Users_Url, headers=SCIM_headers, data=json.dumps(AddDatas))
                resp.raise_for_status()
                print(f"User added to PRA : {user['EMAIL']}")

        PRAUserData = await get_pra_users()

        # Delete users that are not in Azure AD anymore
        for praUser in PRAUserData:
            if not any(u["EMAIL"] == praUser["EMAIL"] for u in UserData):
                delete_url = f"{Users_Url}/{praUser['ID']}"
                resp = await client.delete(delete_url, headers=SCIM_headers)
                resp.raise_for_status()
                print(f"User removed from PRA : {praUser['EMAIL']}")

        PRAUserData = await get_pra_users()

        # Only get users that are part of a group in Azure
        group_members_from_azure = [u for u in UserData if "GROUP" in u]

        # Get the updated list of groups in PRA
        PRAGroupData = await get_pra_groups()

        # Update members of each group in PRA
        for azGroup in GroupData:
            azGroupMembers = [u for u in group_members_from_azure if u.get("GROUP") == azGroup["ID"]]
            PRAgroup = next((pg for pg in PRAGroupData if pg["NAME"] == azGroup["NAME"]), None)
            if PRAgroup is None:
                continue

            # Get the PRA IDs of the corresponding users
            PRAMembers = []
            for azUser in azGroupMembers:
                praUser = next((pu for pu in PRAUserData if pu["EMAIL"] == azUser["EMAIL"]), None)
                if praUser:
                    PRAMembers.append({"value": praUser["ID"]})

            PRAMembersForComparison = [m["value"] for m in PRAMembers]

            # Comparing the current PRA group members with the ones we want
            current_members = PRAgroup.get("MEMBERS", [])
            need_update = set(current_members) != set(PRAMembersForComparison)

            if need_update:
                UpdateDatas = {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                    "displayName": PRAgroup["NAME"],
                    "id": PRAgroup["ID"],
                    "members": PRAMembers
                }
                update_url = f"{Groups_Url}/{PRAgroup['ID']}"
                resp = await client.put(update_url, headers=SCIM_headers, data=json.dumps(UpdateDatas))
                resp.raise_for_status()
                print(f"Members updated in group : {PRAgroup['NAME']}")

if __name__ == "__main__":
    asyncio.run(main())
