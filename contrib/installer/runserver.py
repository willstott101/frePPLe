#!/usr/bin/env python

#
# Copyright (C) 2007 by Johan De Taeye
#
# This library is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA
#

# file : $URL$
# revision : $LastChangedRevision$  $LastChangedBy$
# date : $LastChangedDate$
# email : jdetaeye@users.sourceforge.net

import sys, os, os.path, socket
from stat import S_ISDIR, ST_MODE
from optparse import OptionParser, OptionValueError
from django.core.handlers.wsgi import WSGIHandler
from django.core.servers.basehttp import AdminMediaHandler
from django.core.management import execute_from_command_line
from cherrypy.wsgiserver import CherryPyWSGIServer

# Import django settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'freppledb.settings'
from django.conf import settings

# Define the command line options
parser = OptionParser(
  version='frepple %s' % settings.FREPPLE_VERSION,
  usage= '''usage: %prog [options] [action]

Actions:
  runserver      Run the web server.
                 This is the default action.
  shell          Run an interactive Python interpreter.
  dbshell        Run an interactive SQL session on the database.
  syncdb         Create the database tables.
  test           Run the test suite.
''',
  )
parser.add_option("-m", "--model", dest="model",
                  help="Frepple home directory.", type="string")
parser.add_option("-p", "--port", dest="port", default=8000,
                  help="Port number of the server.", type="int")
parser.add_option("-a", "--address", dest="address",
                  help="IP address for the server to listen.", type="string",
                  default=socket.getaddrinfo(socket.gethostname(), None)[0][4][0])

# Parse the command line
(options, args) = parser.parse_args()

# Validate the model directory
if options.model == None:
  if 'FREPPLE_HOME' in os.environ:
    options.model = default=os.environ['FREPPLE_HOME']
  else:
    print 'Missing frepple model directory'
    sys.exit(1)
if not os.path.exists(options.model)or not S_ISDIR(os.stat(options.model)[ST_MODE]):
  print "Directory %s doesn't exist" % options.model
  sys.exit(1)

# Validate the address and port number
try:
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.bind( (options.address, options.port) )
  s.close()
except socket.error, e:
  print 'Invalid address and/or port: %s' % e
  sys.exit(1)

# Update the root directory of the application
settings.FREPPLE_APP = os.path.split(sys.path[0])[0]

# Override the debugging settings
settings.DEBUG = False
settings.TEMPLATE_DEBUG = False

# Update the directories where fixtures are searched
settings.FIXTURE_DIRS = (
  os.path.join(settings.FREPPLE_APP,'fixtures').replace('\\','/'),
)

# Update the template dirs
settings.TEMPLATE_DIRS = (
    # Always use forward slashes, even on Windows.
    os.path.join(settings.FREPPLE_APP,'templates2').replace('\\','/'),
    os.path.join(settings.FREPPLE_APP,'templates1').replace('\\','/'),
    settings.FREPPLE_HOME.replace('\\','/'),
)

# Create the database if it doesn't exist yet
if settings.DATABASE_ENGINE == 'sqlite3' and not os.path.isfile(settings.DATABASE_NAME):
  print "\nDatabase %s doesn't exist." % settings.DATABASE_NAME
  confirm = raw_input("Do you want to create it now? (yes/no): ")
  while confirm not in ('yes', 'no'):
    confirm = raw_input('Please enter either "yes" or "no": ')
  if confirm == 'yes':
    # Create the database
    execute_from_command_line(argv=['','syncdb'])
    sys.exit(0)

# Do the action
try:
  action = args[0]
  if action == 'shell':
    # Runs a Python interactive interpreter.
    execute_from_command_line(argv=['','shell'])
    sys.exit(0)
  elif action == 'dbshell':
    # Runs a Python interactive interpreter.
    execute_from_command_line(argv=['','dbshell'])
    sys.exit(0)
  elif action == 'syncdb':
    # Initializes a database
    execute_from_command_line(argv=['','syncdb'])
    sys.exit(0)
  elif action == 'test':
    # Run the test suite
    execute_from_command_line(argv=['','test'])
    sys.exit(0)
  elif action != 'runserver':
    # Unsupported action
    print "Invalid action '%s'" % action
    parser.print_help()
    sys.exit(1)
except IndexError:
  pass

# Running the cherrypy wsgi server is the default action

# Print a header message
print 'Running Frepple %s with database %s\n' % (settings.FREPPLE_VERSION,settings.DATABASE_NAME)
print 'To access the server, point your browser to http://%s:%s/' % (options.address, options.port)
print 'The defautl user name and password are "frepple"\n'
print 'Quit the server with CTRL-C.\n'

# Run the WSGI server
server = CherryPyWSGIServer(
  (options.address, options.port),
  AdminMediaHandler(WSGIHandler(), os.path.join(settings.FREPPLE_APP,'media'))
  )
try:
  server.start()
except KeyboardInterrupt:
  server.stop()
