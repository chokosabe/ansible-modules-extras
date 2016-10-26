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
module: ecs_taskdefinition_facts
short_description: Gather facts about ECS task definitions in AWS
description:
    - Gather facts about ECS task definitions in AWS
version_added: "2.2"
author: "Rob White (@wimnat)"
options:
  family_prefix:
    description:
      - Specifying a family_prefix limits the listed task definitions to task definition revisions that belong to that family.
    required: true
    default: null
  status:
    description:
      - The task definition status with which to filter the results. By default, only ACTIVE task definitions are listed. By setting this parameter to INACTIVE, you can view task definitions that are INACTIVE as long as an active task or service still references them.
    required: false
    default: ACTIVE
    choices: [ 'ACTIVE', 'INACTIVE' ]
notes:
  - You can only describe INACTIVE task definitions while an active task or service references them.
  - If the family_prefix is not matched then an empty list will be returned.
  - The status parameter is case sensitive

extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Gather facts about active task definitions in the family my-taskdef
- ecs_taskdefinition_facts:
    family_prefix: my-taskdef

# Gather facts about active task definitions in the family my-taskdef.
- ecs_taskdefinition_facts:
    family_prefix: my-taskdef
    status: INACTIVE
'''

RETURN = '''
container_definitions:
    description: A list of container definitions in JSON format that describe the different containers that make up your task.
    type: list
    sample: []
task_definition_arn:
    description: The full Amazon Resource Name (ARN) of the task definition.
    type: string
    sample: "arn:aws:iam::01234567890:role/myrole"
family:
    description: The family of your task definition, used as the definition name.
    type: string
    sample: mytask
task_role_arn:
    description: The Amazon Resource Name (ARN) of the IAM role that containers in this task can assume. All containers in this task are granted the permissions that are specified in this role.
    type: string
    sample: "arn:aws:iam::01234567890:task-definition/mytask:1"
network_mode:
    description: The Docker networking mode to use for the containers in the task.
    type: string
    sample: bridge
revision:
    description: The revision of the task in a particular family. The revision is a version number of a task definition in a family.
    type: int
    sample: 1
volumes:
    description: The list of volumes in a task.
    type: list
    sample: []
status:
    description: The status of the task definition.
    type: string
    sample: My important backup
requires_attributes:
    description: The container instance attributes required by your task.
    type: list
    sample: []
'''

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, ParamValidationError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import (ansible_dict_to_boto3_filter_list,
        boto3_conn, boto3_tag_list_to_ansible_dict, camel_dict_to_snake_dict,
        ec2_argument_spec, get_aws_connection_info)


def list_ecs_task_definitions(connection, module):

    family_prefix = module.params.get("family_prefix")
    status = module.params.get("status")

    try:
        task_definitions = connection.list_task_definitions(familyPrefix=family_prefix, status=status, maxResults=10)
    except (ClientError, ParamValidationError) as e:
        module.fail_json(msg=e.message)

    task_definitions_complete = task_definitions['taskDefinitionArns']

    # Handle large responses
    while 'nextToken' in task_definitions:
        task_definitions = connection.list_task_definitions(familyPrefix=family_prefix, status=status, nextToken=task_definitions['nextToken'])
        task_definitions_complete = task_definitions_complete + task_definitions['taskDefinitionArns']

    task_definitions_detail = []
    for task in task_definitions_complete:
        try:
            task_definitions_detail.append(camel_dict_to_snake_dict(connection.describe_task_definition(taskDefinition=task)['taskDefinition']))
        except (ClientError, ParamValidationError) as e:
            module.fail_json(msg=e.message)

    module.exit_json(task_definitions=task_definitions_detail)


def main():

    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            family_prefix=dict(required=True, type='str'),
            status=dict(required=False, default='ACTIVE', choices=['ACTIVE', 'INACTIVE'], type='str')
        )
    )

    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)

    if region:
        connection = boto3_conn(module, conn_type='client', resource='ecs', region=region, endpoint=ec2_url, **aws_connect_params)
    else:
        module.fail_json(msg="region must be specified")

    list_ecs_task_definitions(connection, module)


if __name__ == '__main__':
    main()
