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

import os
import shutil
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connections, transaction, DEFAULT_DB_ALIAS
from django.conf import settings
from django.utils.translation import ugettext as _

from execute.models import log


class Command(BaseCommand):
  help = '''
  This command copies the contents of a database into another.
  The original data in the destination database are lost.
  '''
  option_list = BaseCommand.option_list + (
    make_option('--user', dest='user', type='string',
      help='User running the command'),
    make_option('--nonfatal', action="store_true", dest='nonfatal', 
      default=False, help='Dont abort the execution upon an error'),
    )
  args = 'source_database destination_database'

  requires_model_validation = False

  def get_version(self):
    return settings.FREPPLE_VERSION

  @transaction.commit_manually
  def handle(self, *args, **options):
    # Make sure the debug flag is not set!
    # When it is set, the django database wrapper collects a list of all sql
    # statements executed and their timings. This consumes plenty of memory
    # and cpu time.
    tmp_debug = settings.DEBUG
    settings.DEBUG = False

    # Pick up options
    if 'user' in options: user = options['user'] or ''
    else: user = ''
    nonfatal = False
    if 'nonfatal' in options: nonfatal = options['nonfatal']
    
    # Validate the arguments
    if len(args) != 2:
      raise CommandError("Command takes exactly 2 arguments.")
    source = args[0]
    if source not in settings.DATABASES.keys():
      raise CommandError("No source database defined with name '%s'" % source)
    destination = args[1]
    if destination not in settings.DATABASES.keys():
      raise CommandError("No destination database defined with name '%s'" % destination)
    if source == destination:
      raise CommandError("Can't copy a schema on itself")
    if settings.DATABASES[source]['ENGINE'] != settings.DATABASES[destination]['ENGINE']:
      raise CommandError("Source and destination databases have a different engine")    

    try:
      # Logging message
      log(category='COPY', theuser=user,
        message=_("Start copying database '%(source)s' to '%(destination)s'" % 
          {'source':source, 'destination':destination} )).save()
      transaction.commit()
      
      # Copying the data  
      if settings.DATABASES[source]['ENGINE'] == 'django.db.backends.postgresql_psycopg2':
        # Prerequisites:
        # * pg_dump and psql need to be in the path
        # * The passwords need to be specified upfront in a file ~/.pgpass:
        #      hostname:port:database:username:password
        ret = os.system("pg_dump -c -U%s -Fp %s%s%s | psql -U%s %s%s%s" % (
          settings.DATABASES[source]['USER'],
          settings.DATABASES[source]['HOST'] and ("-h %s " % settings.DATABASES[source]['HOST']) or '',
          settings.DATABASES[source]['PORT'] and ("-p %s " % settings.DATABASES[source]['PORT']) or '',
          settings.DATABASES[source]['NAME'],
          settings.DATABASES[destination]['USER'],
          settings.DATABASES[destination]['HOST'] and ("-h %s " % settings.DATABASES[destination]['HOST']) or '',
          settings.DATABASES[destination]['PORT'] and ("-p %s " % settings.DATABASES[destination]['PORT']) or '',
          settings.DATABASES[destination]['NAME'],
          ))      
        if ret: raise Exception('Exit code of the database copy command is %d' % ret)
      elif settings.DATABASES[source]['ENGINE'] == 'django.db.backends.sqlite3':
        # A plain copy of the database file
        shutil.copy2(settings.DATABASES[source]['NAME'], settings.DATABASES[destination]['NAME'])
      elif settings.DATABASES[source]['ENGINE'] == 'django.db.backends.mysql':
        # Prerequisites:
        # * mysqldump and mysql need to be in the path
        ret = os.system("mysqldump %s --password=%s --user=%s %s%s--quick --compress --extended-insert --add-drop-table | mysql %s --password=%s --user=%s %s%s" % (
          settings.DATABASES[source]['NAME'],
          settings.DATABASES[source]['PASSWORD'],
          settings.DATABASES[source]['USER'],
          settings.DATABASES[source]['HOST'] and ("--host=%s " % settings.DATABASES[source]['HOST']) or '',
          settings.DATABASES[source]['PORT'] and ("--port=%s " % settings.DATABASES[source]['PORT']) or '',
          settings.DATABASES[destination]['NAME'],
          settings.DATABASES[destination]['PASSWORD'],
          settings.DATABASES[destination]['USER'],
          settings.DATABASES[destination]['HOST'] and ("--host=%s " % settings.DATABASES[destination]['HOST']) or '',
          settings.DATABASES[destination]['PORT'] and ("--port=%s " % settings.DATABASES[destination]['PORT']) or '',
          ))      
        if ret: raise Exception('Exit code of the database copy command is %d' % ret)
      elif settings.DATABASES[source]['ENGINE'] == 'django.db.backends.oracle':
        # Prerequisites:
        # * impdp and expdp need to be in the path
        # * DBA has to create a server side directory and grant rights to it:
        #    CREATE OR REPLACE DIRECTORY dump_dir AS 'c:\temp';
        #    GRANT READ, WRITE ON DIRECTORY dump_dir TO usr1;
        #    GRANT READ, WRITE ON DIRECTORY dump_dir TO usr2;
        # * If the schemas reside on different servers, the DB will need to
        #   create a database link. 
        #   If the database are on the same server, you might still use the database
        #   link to avoid create a temporary dump file.
        # * Can't be run multiple copies in parallel
        try:
          try: os.unlink('c:\\temp\\frepple.dmp')
          except: pass
          ret = os.system("expdp %s/%s@//%s:%s/%s schemas=%s directory=dump_dir nologfile=Y dumpfile=frepple.dmp" % (
            settings.DATABASES[source]['USER'],
            settings.DATABASES[source]['PASSWORD'],
            settings.DATABASES[source]['HOST'],
            settings.DATABASES[source]['PORT'],
            settings.DATABASES[source]['NAME'],
            settings.DATABASES[source]['USER'],
            ))          
          if ret: raise Exception('Exit code of the database export command is %d' % ret)
          ret = os.system("impdp %s/%s@//%s:%s/%s remap_schema=%s:%s table_exists_action=replace directory=dump_dir nologfile=Y dumpfile=frepple.dmp" % (
            settings.DATABASES[destination]['USER'],
            settings.DATABASES[destination]['PASSWORD'],
            settings.DATABASES[destination]['HOST'],
            settings.DATABASES[destination]['PORT'],
            settings.DATABASES[destination]['NAME'],
            settings.DATABASES[source]['USER'],
            settings.DATABASES[destination]['USER'],
            ))
          if ret: raise Exception('Exit code of the database import command is %d' % ret)
        finally:
          try: os.unlink('c:\\temp\\frepple.dmp')
          except: pass
      else:
        raise Exception('Copy command not supported for database engine %s' % settings.DATABASES[source]['ENGINE'])
                      
      # Logging message
      log(category='COPY', theuser=user,
        message=_("Finished copying database '%(source)s' to '%(destination)s'" % 
          {'source':source, 'destination':destination} )).save()      
    except Exception, e:
      try: log(category='COPY', theuser=user,
        message=_("Failed copying database '%(source)s' to '%(destination)s'" % 
          {'source':source, 'destination':destination} )).save()
      except: pass
      if nonfatal: raise e
      else: raise CommandError(e)
      
    finally:
      transaction.commit()
      settings.DEBUG = tmp_debug