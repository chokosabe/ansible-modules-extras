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
$filter_patterns = @('public-keys')

# result
$result = New-Object psobject @{
    changed = $FALSE
}

Function _Fetch($url) {

    try {
	    Invoke-RestMethod -Uri $url
        return
    } catch [System.Net.WebException] {
        return $null
    }
	
}

$global:temp_data = @{}

Function Fetch($uri, $_data=@{}) {

    $sg_fields = @()
    $raw_subfields = (_Fetch $uri)

    if (!$raw_subfields) {
        return
    }
    
    $subfields = ($raw_subfields -split '[\n]') |? {$_}

    foreach ($field in $subfields) {
        If ($field.EndsWith("/")) {
            #Set-Variable -Name $global:var1 -Value (Fetch($uri + $field)) -Scope Global
            #$_data = $data + (Fetch($uri + $field))
            $x = Fetch($uri + $field)
            try {
                $global:temp_data =  $global:temp_data + $x
            } catch [System.ArgumentException] {
                
            }
        }
        
        If ($uri.EndsWith("/")) {
            $new_uri = $uri + $field
        } Else {
            $new_uri = $uri + "/" + $field
        }

        If (($new_uri -notlike "*=*") -or (-Not ($new_uri.EndsWith("/")))) {
            $content = _Fetch($new_uri)
            if ($field -eq "security-groups") {
                $sg_fields += ($content -split '[\n]') -join ","
                $_data[$new_uri] = $sg_fields
            } Else {
                $_data[$new_uri] = $content
            }
        }
    }

    return $_data + $global:temp_data

}

Function Mangle_Fields([Hashtable]$fieldsxx, $uri) {
    
    Write-Host $fieldsxx.gettype()
    #Write-Host ($fields | Out-String)
    $new_fields = @{}
    #foreach ($field in $fields.GetEnumerator()) {
    $fields.GetEnumerator() | % {
        Write-Host "$($_.key)"
    }
}


$_data = Fetch($ec2_metadata_uri)

$new_fields = @{}

# Add Ansible variable prefix
foreach ($field in $_data.GetEnumerator()) {
    #Write-Host "$($field.Name): $($field.Value)"
    $split_fields = $field.Name.Remove(0,$ec2_metadata_uri.length)
    $new_key = "-" + $split_fields
    $new_fields[$prefix + $new_key] = $field.Value
}

# Remove public keys meta
$remove_list = @()
foreach ($pattern in $filter_patterns) {
    foreach ($key in $new_fields.Keys) {
        Write-Output $key
        Write-Output $pattern
        if ($key -like "*" + $pattern + "*") {
            $remove_list += $key
        }
    }
}
foreach ($item in $remove_list) {
    $new_fields.Remove($item)
}

$final_fields = @{}
# Fix invalid var names
foreach ($field in $new_fields.GetEnumerator()) {
    $new_field = $field.Name -replace ":", "_"
    $new_field = $new_field -replace "-", "_"
    $final_fields[$new_field] = $field.Value
    #$new_fields.Remove($field)
    Write-Host $new_field
    #Write-Host "$($field.Name): $($field.Value)"
}

Exit-Json $final_fields

#Write-Host ($final_fields | Format-Table -Wrap | Out-String)

#Write-Host $_data.GetType()

#Mangle_Fields([Hashtable]$_data, $ec2_metadata_uri)


#Write-Host ($_data | Format-Table -Wrap | Out-String)

#Write-Host $global:var1.GetType()
#Write-Host ($global:var1 | Format-Table -Wrap | Out-String)
