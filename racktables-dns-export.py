#!/usr/bin/env python
import MySQLdb
import datetime
import argparse
import os

# Arguments
parser = argparse.ArgumentParser(description='Generate DNS zones files')
parser.add_argument('--zonedest', help='Path to store the zones files to', default='/tmp')
args = parser.parse_args()

con = MySQLdb.connect('localhost', 'user', 'pass', 'racktablesdb')

queries={
  # Get A records (fqdns) from RackTables
  'a':""" SELECT AttributeValue.string_value fqdn,INET_NTOA(IPv4Allocation.ip) ip 
  FROM Object 
  LEFT JOIN IPv4Allocation ON IPv4Allocation.object_id=Object.id 
  LEFT JOIN AttributeValue ON AttributeValue.object_id=Object.id 
  WHERE objtype_id IN        ( SELECT dict_key FROM Dictionary WHERE dict_value IN ( 'Server','VM','Network security') )
  AND AttributeValue.attr_id=( SELECT id FROM Attribute WHERE name='FQDN') 
  AND ip IS NOT NULL 
  GROUP BY fqdn 
  ORDER BY ip ; """,
  # Get aliases
  'cname':""" SELECT attr_fqdn.string_value, attr_alias.string_value 
  FROM AttributeValue attr_alias 
  LEFT JOIN AttributeValue attr_fqdn ON attr_fqdn.object_id=attr_alias.object_id 
  
  WHERE attr_alias.attr_id = ( SELECT id FROM Attribute WHERE name='DNS aliases')
  AND attr_fqdn.attr_id=     ( SELECT id FROM Attribute WHERE name='FQDN'); 
  """, }

header="""$TTL 1D
@                     IN SOA    master.example.com.  root.example.com. (
                      {0}; serial number YYYYMMDDSEQ
                      3600      ; Refresh ( 1 hour)
                      600       ; Retry   (15 min)
                      1209600   ; Expire  ( 2 weeks)
                      1800      ; Min TTL (30 min)
                      )         ; 
                      NS        dns1.example1.com.
                      NS        dns1.example1.com.
""".format(datetime.datetime.today().strftime('%Y%m%d%H'))

# Get data base stuff
with con:
  # Get A records
  a_cur = con.cursor()
  a_cur.execute(queries['a'])
  dns_a_records = a_cur.fetchall()

  # Get aliases
  c_cur = con.cursor()
  c_cur.execute(queries['cname'])
  dns_cname_records = c_cur.fetchall()
  dns_cname_dict=dict( (a,b) for a,b in dns_cname_records )

# Build forward zones file
with open("{0}{1}{2}.txt".format( args.zonedest, os.sep, 'example.com' ) ,'w') as f:
  # Header
  f.write(header)

  # Process A records
  curip=previp=None
  for record in dns_a_records:
    fqdn=record[0]
    name=fqdn.replace(".example.com",'')
    ip=record[1]

    # New line after all records for host
    curip='.'.join( ip.split('.')[0:3] )
    if curip != previp:
      f.write("\n")
    previp=curip
    
    # Forward write
    f.write("{0:<22}IN A     {1}\n".format( name, record[1]))

    # Cnames
    if dns_cname_dict.has_key(fqdn):
      cnames=dns_cname_dict[fqdn].split(',')
      for cname in cnames:
        f.write("{0:<22}IN CNAME {1}\n".format( cname, name) ) 

# Reversed
with open("{0}{1}{2}.txt".format( args.zonedest, os.sep, '10.in-addr.arpa' ) ,'w') as r:
  r.write(header)

  for record in dns_a_records:
    fqdn=record[0]
    ip=record[1]

    # New line after all records for host (no DRY, sorry)
    curip='.'.join( ip.split('.')[0:3] )
    if curip != previp:
      r.write("\n")
    previp=curip

    # Reversed 10. zone
    r.write("{0:<22}IN PTR {1}.\n".format( '.'.join( tuple( reversed ( ip.split('.')[1:4] ) ) ) , fqdn))
