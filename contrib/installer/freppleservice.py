#
# Copyright (C) 2010 by Johan De Taeye
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
# Foundation Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#

# file : $URL$
# revision : $LastChangedRevision$  $LastChangedBy$
# date : $LastChangedDate$

import sys
import os
import socket
from datetime import datetime

import win32serviceutil
import win32service
import servicemanager

# TODO event log not nice: eventmessagefile (stored in registry) is not valid (refers to file inside zip file)

class frePPLeService(win32serviceutil.ServiceFramework):

    _svc_name_ = "frepple-service"
    _svc_display_name_ = "frePPLe web server"
    _svc_description_ = "Runs a web server for frePPLe"

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # Stop CherryPy server
        self.server.stop()
        # Log stop event
        msg = "frePPLe web server stopped"
        servicemanager.LogInfoMsg(msg)
        print datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg
        
    def SvcDoRun(self):
        # Environment settings (which are used in the Django settings file and need
        # to be updated BEFORE importing the settings)
        os.environ['DJANGO_SETTINGS_MODULE'] = 'freppledb.settings'
        os.environ['FREPPLE_APP'] = os.path.split(sys.path[0])[0]
        os.environ['FREPPLE_HOME'] = os.path.abspath(os.path.dirname(sys.argv[0]))
        
        # Sys.path contains the zip file with all packages. We need to put the
        # freppledb subdirectory from the zip-file separately on the path because
        # our django applications never refer to the project name.
        sys.path = [ os.path.join(sys.path[0],'freppledb'), sys.path[0] ]
        
        # Import modules
        from django.conf import settings
        import cherrypy
        from cherrypy.wsgiserver import CherryPyWSGIServer
        import django
        from django.core.handlers.wsgi import WSGIHandler
        from django.core.servers.basehttp import AdminMediaHandler        
        from stat import S_ISDIR, ST_MODE
        
        # Override the debugging settings
        settings.DEBUG = False
        settings.TEMPLATE_DEBUG = False
        settings.STANDALONE = True
        
        # Update the directories where fixtures are searched
        settings.FIXTURE_DIRS = (
          os.path.join(settings.FREPPLE_APP,'fixtures','input').replace('\\','/'),
          os.path.join(settings.FREPPLE_APP,'fixtures','common').replace('\\','/'),
        )
        
        # Update the template dirs
        settings.TEMPLATE_DIRS = (
            # Always use forward slashes, even on Windows.
            os.path.join(settings.FREPPLE_APP,'templates2').replace('\\','/'),
            os.path.join(settings.FREPPLE_APP,'templates1').replace('\\','/'),
            settings.FREPPLE_HOME.replace('\\','/'),
        )        
        
        # Pick up port and adress
        try: address = socket.gethostbyname(socket.gethostname())
        except: address = '127.0.0.1'
        port = settings.PORT
        
        # Update the directories where fixtures are searched
        settings.FIXTURE_DIRS = (
          os.path.join(settings.FREPPLE_APP,'fixtures','input').replace('\\','/'),
          os.path.join(settings.FREPPLE_APP,'fixtures','common').replace('\\','/'),
        )
        
        # Update the template dirs
        settings.TEMPLATE_DIRS = (
            # Always use forward slashes, even on Windows.
            os.path.join(settings.FREPPLE_APP,'templates2').replace('\\','/'),
            os.path.join(settings.FREPPLE_APP,'templates1').replace('\\','/'),
            settings.FREPPLE_HOME.replace('\\','/'),
        )
        
        cherrypy.config.update({
            'global':{
                'log.screen': False,
                'tools.log_tracebacks.on': True,
                'engine.autoreload.on': False,
                'engine.SIGHUP': None,
                'engine.SIGTERM': None
                }
            })
        self.server = CherryPyWSGIServer((address, port),
          AdminMediaHandler(WSGIHandler(), os.path.join(settings.FREPPLE_APP,'media'))
          )

        # Redirect all output and log a start event
        try:
          log = os.path.join(settings.FREPPLE_APP,'server.log')
          sys.stdout = open(log, 'a', 0)
          msg = "frePPLe web server listening on http://%s:%d and logging to %s" % (address, port, log)
          servicemanager.LogInfoMsg(msg)
          print datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg
          print os.environ['FREPPLE_APP'], os.environ['FREPPLE_HOME']
        except:
          # Too bad if we can't write log info
          servicemanager.LogInfoMsg("frePPLe web server listening on http://%s:%d without log file" % (address, port))

        # Infinite loop serving requests
        try:
          self.server.start()
        except Exception, e:
          # Log an error event
          msg = "frePPLe web server failed to start:\n%s" % e
          servicemanager.LogErrorMsg(msg)
          print datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg
        

if __name__=='__main__':
    # Do with the service whatever option is passed in the command line
    win32serviceutil.HandleCommandLine(frePPLeService)
    