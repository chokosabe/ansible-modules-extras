#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: iam_user
short_description: Manage AWS IAM users
description:
  - Manage AWS IAM roles
version_added: "2.2"
author: Rob White, @wimnat
options:
  path:
    description:
      - The path to the user. For more information about paths, see U(http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html).
    required: false
    default: "/"
  name:
    description:
      - The name of the user.
    required: true
  password:
    description:
      - The password of the user.
  password_update_policy:
    description:
      - Whether to always update the user password, or only when the user is created for the first time.
    required: false
    default: always
    choices: [ 'always', 'on_create' ]
  ssh_public_key:
    description:
      - The SSH public key. The public key must be encoded in ssh-rsa format or PEM format. It is used for authenticating a user to AWS CodeCommit.
    required: false
  managed_policy:
    description:
      - A list of managed policy ARNs (can't use friendly names due to AWS API limitation) to attach to the user. To embed an inline policy, use M(iam_policy). To remove existing policies, use an empty list item.
    required: true
  state:
    description:
      - Create or remove the IAM user.
    required: true
    choices: [ 'present', 'absent' ]
requirements: [ botocore, boto3 ]
extends_documentation_fragment:
  - aws
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Create a user
- iam_user:
    name: joe.blogs
    state: present

# Create a user and attach a managed policy called "PowerUserAccess"
- iam_user:
    name: joe.blogs
    state: present
    managed_policy:
      - arn:aws:iam::aws:policy/ReadOnlyAccess

# Keep the user created above but remove all managed policies
- iam_user:
    name: joe.blogs
    state: present
    managed_policy:
      -

# Delete the user
- iam_user:
    name: joe.blogs
    state: absent

'''
RETURN = '''
activeServicesCount:
    description: how many services are active in this cluster
    returned: 0 if a new cluster
    type: int
clusterArn:
    description: the ARN of the cluster just created
    type: string (ARN)
    sample: arn:aws:ecs:us-west-2:172139249013:cluster/test-cluster-mfshcdok
clusterName:
    description: name of the cluster just created (should match the input argument)
    type: string
    sample: test-cluster-mfshcdok
pendingTasksCount:
    description: how many tasks are waiting to run in this cluster
    returned: 0 if a new cluster
    type: int
registeredContainerInstancesCount:
    description: how many container instances are available in this cluster
    returned: 0 if a new cluster
    type: int
runningTasksCount:
    description: how many tasks are running in this cluster
    returned: 0 if a new cluster
    type: int
status:
    description: the status of the new cluster
    returned: ACTIVE
    type: string
'''

import json

try:
    import boto3
    from botocore.exceptions import ClientError, ParamValidationError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def compare_assume_role_policy_doc(current_policy_doc, new_policy_doc):

    # Get proper JSON strings for both docs
    current_policy_doc = json.dumps(current_policy_doc)
    new_policy_doc = json.dumps(json.loads(new_policy_doc))

    if current_policy_doc == new_policy_doc:
        return True
    else:
        return False


def compare_attached_user_policies(current_attached_policies, new_attached_policies):

    # If new_attached_policies is None it means we want to remove all policies
    if len(current_attached_policies) > 0 and new_attached_policies is None:
        return False

    current_attached_policies_arn_list = []
    for policy in current_attached_policies:
        current_attached_policies_arn_list.append(policy['PolicyArn'])

    if set(current_attached_policies_arn_list) == set(new_attached_policies):
        return True
    else:
        return False


def create_or_update_user(connection, module):

    params = dict()
    params['Path'] = module.params.get('path')
    params['UserName'] = module.params.get('name')
    managed_policies = module.params.get('managed_policy')
    changed = False

    # Get role
    user = get_user(connection, params['UserName'])

    # If user is None, create it
    if user is None:
        try:
            user = connection.create_user(**params)
            changed = True
        except (ClientError, ParamValidationError) as e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))
    else:
        # Check attached managed policies
        current_attached_policies = get_attached_policy_list(connection, params['RoleName'], module)
        if not compare_attached_user_policies(current_attached_policies, managed_policies):
            # If managed_policies has a single empty element we want to remove all attached policies
            if len(managed_policies) == 1 and managed_policies[0] == "":
                for policy in current_attached_policies:
                    try:
                        connection.detach_user_policy(RoleName=params['RoleName'], PolicyArn=policy['PolicyArn'])
                    except (ClientError, ParamValidationError) as e:
                        module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

            # Detach policies not present
            current_attached_policies_arn_list = []
            for policy in current_attached_policies:
                current_attached_policies_arn_list.append(policy['PolicyArn'])

            for policy_arn in list(set(current_attached_policies_arn_list) - set(managed_policies)):
                try:
                    connection.detach_role_policy(RoleName=params['RoleName'], PolicyArn=policy_arn)
                except (ClientError, ParamValidationError) as e:
                    module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

            # Attach each policy
            for policy_arn in managed_policies:
                try:
                    connection.attach_role_policy(RoleName=params['RoleName'], PolicyArn=policy_arn)
                except (ClientError, ParamValidationError) as e:
                    module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

            changed = True

    # We need to remove any instance profiles from the role before we delete it
    try:
        instance_profiles = connection.list_instance_profiles_for_role(RoleName=params['RoleName'])['InstanceProfiles']
    except ClientError as e:
        module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))
    if not any(p['InstanceProfileName'] == params['RoleName'] for p in instance_profiles):
        # Make sure an instance profile is attached
        try:
            connection.create_instance_profile(InstanceProfileName=params['RoleName'], Path=params['Path'])
            changed = True
        except ClientError as e:
            # If the profile already exists, no problem, move on
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                pass
            else:
                module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))
        connection.add_role_to_instance_profile(InstanceProfileName=params['RoleName'], RoleName=params['RoleName'])

    # Get the role again
    role = get_user(connection, params['RoleName'])

    role['attached_policies'] = get_attached_policy_list(connection, params['RoleName'], module)
    module.exit_json(changed=changed, iam_role=camel_dict_to_snake_dict(role))


def destroy_user(connection, module):

    params = dict()
    params['RoleName'] = module.params.get('name')

    if get_role(connection, params['RoleName']):

        # We need to remove any instance profiles from the role before we delete it
        try:
            instance_profiles = connection.list_instance_profiles_for_role(RoleName=params['RoleName'])['InstanceProfiles']
        except ClientError as e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

        # Now remove the role from the instance profile(s)
        for profile in instance_profiles:
            try:
                connection.remove_role_from_instance_profile(InstanceProfileName=profile['InstanceProfileName'], RoleName=params['RoleName'])
            except ClientError as e:
                module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

        try:
            connection.delete_role(**params)
        except ClientError as e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))
    else:
        module.exit_json(changed=False)

    module.exit_json(changed=True)


def get_user(connection, name, module):

    params = dict()
    params['UserName'] = name

    try:
        return connection.get_user(**params)['User']
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            return None
        else:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))


def get_attached_policy_list(connection, name, module):

    try:
        return connection.list_attached_user_policies(UserName=name)['AttachedPolicies']
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            return None
        else:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))


def main():

    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            name=dict(required=True, type='str'),
            path=dict(default="/", required=False, type='str'),
            managed_policy=dict(default=[], required=False, type='list'),
            state=dict(default=None, choices=['present', 'absent'], required=True)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           required_if=[
                               ('state', 'present', ['assume_role_policy_document'])
                           ]
                           )

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)

    connection = boto3_conn(module, conn_type='client', resource='iam', region=region, endpoint=ec2_url, **aws_connect_params)

    state = module.params.get("state")

    if state == 'present':
        create_or_update_user(connection, module)
    else:
        destroy_user(connection, module)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
