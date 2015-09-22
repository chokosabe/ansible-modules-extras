#!powershell
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

# WANT_JSON
# POWERSHELL_COMMON

#$params = Parse-Args $args

$ec2_metadata_uri = 'http://169.254.169.254/latest/meta-data/'
$ec2_sshdata_uri  = 'http://169.254.169.254/latest/meta-data/public-keys/0/openssh-key'
$ec2_userdata_uri = 'http://169.254.169.254/latest/user-data/'
$global:data = @{}
$prefix = 'ansible_ec2'

# result
$result = New-Object psobject @{
    changed = $FALSE
}

Function _Fetch($url) {

	Invoke-RestMethod -Uri $url
    #Write-Host ($rest_result | Out-String)
	#if ($rest_result.code -eq 200) {
#		$result.Add('bla', $rest_result.message)
#	} else {
#		$result.Add('bla', $rest_result.message)
#    }
    #return
	
}

Function Fetch($uri) {

    $raw_subfields = (_Fetch $uri)
    Write-Host ($raw_subfields | Out-String)
    $subfields = ($raw_subfields -split '[\n]') |? {$_}

    Write-Host $subfields

    foreach ($field in $subfields) {
        If ($field.EndsWith("/")) {
            Fetch($uri + $field)
            #Write-Host $field
        } 
        
        If ($uri.EndsWith("/")) {
            $new_uri = $uri + $field
        } Else {
            $new_uri = $uri + "/" + $field
            #$global:data.Add($field, _Fetch($uri + $field))
            #Write-Host $field
            #Write-Host (_Fetch($uri + $field) | Out-String)
        }
        Write-Host $new_uri
        If (-Not ($new_uri.EndsWith("/"))) {
            Write-Host (_Fetch($new_uri) | Out-String)
        }
    }

}

Write-Host (Fetch($ec2_metadata_uri))

#Write-Host ($result | Out-String)
