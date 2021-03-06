#! /usr/bin/env python
# Python script for the Interoute Virtual Data Centre API:
#   Name: networks_member_listing.py
#   Purpose: List the networks in a VDC with the VMs belonging to each network
#   Requires: class VDCApiCall in the file vdc_api_call.py
# See the repo: https://github.com/Interoute/API-fun-and-education
#
# You can pass options via the command line: type 'python networks_member_listing.py -h'
# for usage information
#
# Copyright (C) Interoute Communications Limited, 2017

from __future__ import print_function
import vdc_api_call as vdc
import sys
import getpass
import json
import os
import string
import datetime
import argparse
import re

if __name__ == '__main__':
    # STEP 1: Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default=os.path.join(os.path.expanduser('~'), '.vdcapi'),
                    help="path/name of the config file to be used for the API URL and API keys (default is ~/.vdcapi)")
    parser.add_argument("-r", "--region", choices=['Europe','europe','USA','usa','Asia','asia'],
                    default='Europe', help="specify the VDC region: Europe, USA or Asia (default Europe)")
    parser.add_argument("-w", "--writediag", action='store_true', help="write a diag file for use with nwdiag")
    parser.add_argument("-f", "--diagfile", default='VDC-network-data.diag',
                    help="name of the output diag file for use with nwdiag")
    parser.add_argument("-z", "--zone", help="filter results by zone name (match by initial characters) ")
    parser.add_argument("-e", "--egress", action='store_true', help="display egress rules for local gateway networks")
    parser.add_argument("-v", "--vmstate", action='store_true', help="display VM state by text colour")
    parser.add_argument("-u", "--uuid", action='store_true', help="display the UUIDs for networks, IP addresses and VMs")  
    vdcRegion = parser.parse_args().region
    writeDiag = parser.parse_args().writediag
    config_file = parser.parse_args().config
    zonenameFilter = parser.parse_args().zone
    showEgress = parser.parse_args().egress
    showVmState =  parser.parse_args().vmstate
    showUUID = parser.parse_args().uuid
    if writeDiag:
       diagfileName = parser.parse_args().diagfile

    # STEP 2: If config file is found, read its content,
    # else query user for the URL, API key, Secret key
    if os.path.isfile(config_file):
        with open(config_file) as fh:
            data = fh.read()
            config = json.loads(data)
            api_url = config['api_url']
            apiKey = config['api_key']
            secret = config['api_secret']
    else:
        print('API url (e.g. http://10.220.18.115:8080/client/api):', end='')
        api_url = raw_input()
        print('API key:', end='')
        apiKey = raw_input()
        secret = getpass.getpass(prompt='API secret:')

    # STEP 3: Create the api access object
    api = vdc.VDCApiCall(api_url, apiKey, secret)

    # STEP 4: API calls to get the information about networks and VMs
    request = {'region': vdcRegion}
    try:
       networksList = api.listNetworks(request)
       if zonenameFilter:
          networksList['network'] = [network for network in networksList['network'] if re.search('\A'+zonenameFilter,network['zonename'])]
          if networksList['network'] == []:
             print("ERROR: No networks found when using the zonename filter \'%s\'." % zonenameFilter)
             sys.exit("FATAL: Program terminating")
    except KeyError:
       print("Error: No networks found", file=sys.stderr)
    try: 
       vmList = api.listVirtualMachines(request)
    except KeyError:
       print("Note: No VMs found for this account", file=sys.stderr)
       vmList = {}
       pass 
    try:
       portForwardingRulesList = api.listPortForwardingRules(request)
    except KeyError:
       print("Note: No port-forwarding rules found for this account")
       portForwardingRulesList = {}
       pass
    try:
       loadBalancerRulesList = api.listLoadBalancerRules(request)
    except KeyError:
       print("Note: No loadbalancer rules found for this account")
       loadBalancerRulesList = {}
       lbRulesWithVM = []
       pass 


    # STEP 5: Process the information from the API calls
    nameStringSubs = string.maketrans(" -","__")
    try:
        checkTime = datetime.datetime.utcnow() # get the current time (UTC = GMT)
        if writeDiag:
           diagfile = open(diagfileName, 'w')
           diagfile.write('nwdiag {\n internet [shape=cloud]\n VDC [shape=cloud] \n internet -- VDC\n')
        print("\nNetwork configuration for the account '%s' in VDC region '%s' checked at %s:" 
            % (networksList['network'][0]['domain'],vdcRegion,checkTime.strftime("%Y-%m-%d %H:%M:%S UTC")))
        if zonenameFilter:
           print("***Results filtered for zone name(s) starting with '%s'" % (zonenameFilter))
        for network in networksList['network']:
            if network['subtype']=='privatedirectconnectwithgatewayservicesegress':
               egressLabel = " (+E)"
            else:
               egressLabel = ""
            if network['name'] != network['displaytext']:
               print(" "+unichr(0x2015)+' \'%s\'|\'%s\' (Zone: %s, CIDR: %s%s' % (
                  network['name'],
                  network['displaytext'],
                  network['zonename'],
                  network['cidr'],
                  egressLabel
                ), end='')
            else:
                print(" "+unichr(0x2015)+' \'%s\' (Zone: %s, CIDR: %s%s' % (
                  network['name'],
                  network['zonename'],
                  network['cidr'],
                  egressLabel
                ), end='')
               
            #FIND EXTERNAL IP ADDRESSES IF THEY EXIST FOR THE NETWORK
            external_IP = {}
            if network['subtype']=='internetgateway':
               testdict=request
               testdict['associatednetworkid']=network['id']
               external_IP=api.listPublicIpAddresses(testdict)
               if external_IP != {}:
                  if external_IP['count']==1:
                     print(", IP: %s)" % external_IP['publicipaddress'][0]['ipaddress'])
                  else: # more than one public IP address for this network
                     for n in range(0,external_IP['count']):
                        print(", IP%s: %s" % (n+1, external_IP['publicipaddress'][n]['ipaddress']), end='')
                     print(")")
               else:
                  print(", IP: UNALLOCATED)")
            else:
               print(")")
            #PRINT UUIDs FOR NETWORK AND IP ADDRESS(ES)
            if showUUID:
               print("   " + unichr(0x2502) + "[networkid=%s" % network['id'], end='')
               if network['subtype']=='internetgateway' and external_IP != {}:
                  if external_IP['count']==1:
                     print(", ipaddressid=%s]" % external_IP['publicipaddress'][0]['id'])
                  else: # more than one public IP address for this network
                     for n in range(0,external_IP['count']):
                        print(", ipaddressid%s=%s" % (n+1, external_IP['publicipaddress'][n]['id']), end='')
                     print("]")
               else: # no ipaddressid values to print
                  print("]")
            #PRINT EGRESS FOR 'PRIVATE DIRECT CONNECT WITH INTERNET EGRESS' NETWORKS
            if network['subtype']=='privatedirectconnectwithgatewayservicesegress':
               print("   " + unichr(0x2502) + "(egress: PRIVATE NETWORK WITH INTERNET EGRESS ON ALL PORTS)")
            #GET AND PRINT EGRESS RULES FOR 'LOCAL WITH GATEWAY' NETWORKS
            if showEgress and network['subtype']=='internetgateway':
               print("   " + unichr(0x2502) + "(egress: ", end='')
               try: 
                  egressrules=api.listEgressFirewallRules({'networkid':network['id']})
               except KeyError:
                  pass
               if egressrules == {}:
                  print("NONE", end='')
               else:
                  for e in egressrules['firewallrule']:
                     if e['protocol']=='all':
                        print("[%s|ALL protocols/ports]" % (e['cidrlist']), end='')
                     elif e['protocol']=='icmp':
                        print("[%s|ICMP|icmptype: %d|icmpcode: %d] " % (e['cidrlist'], e['icmptype'], e['icmpcode']), end='')
                     else:
                        if e['startport'] == e['endport']:
                           print("[%s|%s|port %d]" % (e['cidrlist'], e['protocol'].upper(), e['startport']), end='')
                        else:
                           print("[%s|%s|ports %d:%d]" % (e['cidrlist'], e['protocol'].upper(), e['startport'], e['endport']), end='')
               print(")")
            #GET AND PRINT LOADBALANCER RULES
            lbRulesWithVM = []
            if loadBalancerRulesList != {}:
               lbRulesForNetwork = [lbr for lbr in loadBalancerRulesList['loadbalancerrule'] if lbr['networkid']==network['id']]
               for l in lbRulesForNetwork:
                  print("   " + unichr(0x2502) + "LB: '%s', IP: %s, ports: [%s]->[%s], state: " % (l['name'], l['publicip'], l['publicport'], l['privateport']), end='')
                  try:
                      lVM = api.listLoadBalancerRuleInstances({'id':l['id'], 'region':vdcRegion})
                      print("%d VM" % lVM['count'])
                      # *** POSSIBLE ADDITION: print list of VM IP addresses
                      vmListIds = [lv['id'] for lv in lVM['loadbalancerruleinstance']]
                      lbRulesWithVM = lbRulesWithVM + [{'publicip':l['publicip'], 'publicport':l['publicport'], 'privateport':l['privateport'], 'vmlist':vmListIds}]
                  except KeyError:
                      print("EMPTY")
                      pass
            #PRINT LIST OF MEMBER VMs
            members = []
            if vmList != {}:
               for vm in vmList['virtualmachine']:
                   for i in range(len(vm['nic'])):
                       if network['id'] == vm['nic'][i]['networkid']:
                           members.append([int(vm['nic'][i]['ipaddress'].split('.')[-1]),vm['nic'][i]['ipaddress'],vm['name'],vm['id'],vm['state']])
                           break # Can break out of this loop as soon as the network id is found for a NIC 
            if len(members)>0:
                #For nwdiag, network name has zone city appended
                #(this is helpful because default VDC network names are same in all zones)
                if writeDiag:
                   diagfile.write('network %s_Z_%s {\n address=\"%s\"\n' % (str(network['name']).translate(nameStringSubs),
                      network['zonename'].split()[0], network['cidr']))
                   if external_IP != {}:
                      if external_IP['count']==1:
                         diagfile.write(' VDC [address=\"IP %s\"]\n' % (external_IP['publicipaddress'][0]['ipaddress']))
                      else: # more than one public IP address for this network
                         diagfile.write(' VDC [address=\"IP ')
                         for n in range(0,external_IP['count']-1):
                            diagfile.write('%s, ' % (external_IP['publicipaddress'][n]['ipaddress']))
                         diagfile.write('%s\"]\n' % (external_IP['publicipaddress'][-1]['ipaddress']))
                members.sort() # VMs will be sorted by the last segment of their IP address (=first element of each members list)
                for i in range(len(members)):
                    ###print("DEBUG: %s" % members[i])
                    if i==len(members)-1:  #this is last VM in the network
                       print("   " + unichr(0x2514), end='')
                    else:
                       print("   " + unichr(0x251C), end='')
                    if showVmState:
                       if members[i][4] == 'Running':
                          stateColorOn = "\x1b[32m"
                          stateColorOff = "\x1b[0m"
                       elif members[i][4] == 'Stopped':
                          stateColorOn = "\x1b[31m"
                          stateColorOff = "\x1b[0m"
                       else:
                          stateColorOn = "\x1b[36m"
                          stateColorOff = "\x1b[0m"
                    else:
                       stateColorOn = ""
                       stateColorOff = ""
                    if showUUID:
                       print((" " + stateColorOn + " %s: '%s' [id=%s] " + stateColorOff) % (members[i][1],members[i][2],members[i][3]), end='')
                    else:
                       print((" " + stateColorOn + " %s: '%s'" + stateColorOff) % (members[i][1],members[i][2]), end='')
                    if external_IP != {}:
                       #check for port forwarding rules
                       pfRules = []
                       if portForwardingRulesList != {}: # Test if any port-forwarding rules exist
                          if external_IP['count'] > 1:
                             externalIpMultiple = True
                          else:
                             externalIpMultiple = False
                          for n in range(0,external_IP['count']): 
                              pfRules = pfRules + [p for p in portForwardingRulesList['portforwardingrule'] if 
                                 p['virtualmachineid']==members[i][3] and p['ipaddress']==external_IP['publicipaddress'][n]['ipaddress']] 
                       if pfRules != []:
                          print(" (ports:",end='')
                          for p in pfRules:
                              if p['protocol']=='udp':
                                 udpLabel = "UDP"
                              else:
                                 udpLabel = "" 
                              if externalIpMultiple:
                                 if p['publicport']!=p['publicendport']:
                                    print(" %s[%s:%s/%s]->"%(udpLabel,p['ipaddress'],p['publicport'],p['publicendport']),end='')
                                 else:
                                    print(" %s[%s:%s]->"%(udpLabel,p['ipaddress'],p['publicport']),end='')
                              else:
                                 if p['publicport']!=p['publicendport']:
                                    print(" %s[%s/%s]->"%(udpLabel,p['publicport'],p['publicendport']),end='')
                                 else:
                                    print(" %s[%s]->"%(udpLabel,p['publicport']),end='')
                              if p['privateport']!=p['privateendport']:
                                 print("[%s/%s]"%(p['privateport'],p['privateendport']),end='')
                              else:
                                 print("[%s]"%(p['privateport']),end='')
                          print(")",end='')
                    lbRules = []      
                    if lbRulesWithVM != []:
                       if external_IP['count'] > 1:
                          externalIpMultiple = True
                       else:
                          externalIpMultiple = False
                       for n in range(0,external_IP['count']):
                          lbRules = lbRules + [l for l in lbRulesWithVM if l['publicip']==external_IP['publicipaddress'][n]['ipaddress'] and members[i][3] in l['vmlist']]
                    if lbRules != []:
                          print(" (LBports:",end='')
                          for l in lbRules:
                              if externalIpMultiple:
                                 print(" [%s:%s]->[%s]" % (l['publicip'],l['publicport'],l['privateport']),end='')
                              else:
                                 print(" [%s]->[%s]" % (l['publicport'],l['privateport']),end='')
                          print(")",end='')      
                    print(" ")
                    if writeDiag:
                       diagfile.write('\"%s\" [address=\"%s\"];\n' % (str(members[i][2]).translate(nameStringSubs),members[i][1]))
                if writeDiag:
                   diagfile.write('}\n')
            else:
                print("   *(NO MEMBERS)")
            print(" ")
        if writeDiag:
           diagfile.write("}\n")
           diagfile.close()
                
    except KeyError:
        # if no network exists, " networksList['network'] " will raise exception
        # but other failures of API calls will also raise this exception
        print('***PROGRAM EXIT WITH ERROR: Key Error happened when querying an API call response')
