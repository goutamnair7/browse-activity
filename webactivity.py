# Copyright (C) 2006, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from gettext import gettext as _
import gtk
import logging
import dbus

import _sugar
from sugar.activity import ActivityFactory
from sugar.activity.Activity import Activity
from sugar.clipboard import clipboardservice
from sugar import env
from sugar.graphics import style

import stylesheet
from webview import WebView
from toolbar import Toolbar
from linksmodel import LinksModel
from linksview import LinksView
from linkscontroller import LinksController

_HOMEPAGE = 'file:///home/olpc/Library/index.html'

class WebActivity(Activity):
    def __init__(self, browser=None):
        Activity.__init__(self)

        logging.debug('Starting the web activity')

        self.set_title(_('Web Activity'))

        vbox = gtk.VBox()

        if browser:
            self._browser = browser
        else:
            self._browser = WebView()
        self._browser.connect('notify::title', self._title_changed_cb)

        self._links_model = LinksModel()
        links_view = LinksView(self._links_model, self._browser)

        self._toolbar = Toolbar(self._browser)
        vbox.pack_start(self._toolbar, False)
        self._toolbar.show()

        hbox = gtk.HBox()

        hbox.pack_start(links_view, False)
        hbox.pack_start(self._browser)
        self._browser.show()

        vbox.pack_start(hbox)
        hbox.show()

        self.add(vbox)
        vbox.show()

        self._browser.load_url(_HOMEPAGE)

    def _setup_links_controller(self):
        links_controller = LinksController(self._service, self._links_model)
        self._toolbar.set_links_controller(links_controller)

    def join(self, activity_ps):
        Activity.join(self, activity_ps)

        self._setup_links_controller()

        url = self._service.get_published_value('URL')
        if url:
            self._browser.load_url(url)

    def share(self):
        Activity.share(self)

        self._setup_links_controller()

        url = self._browser.get_location()
        if url:
            self._service.set_published_value('URL', url)

    def execute(self, command, args):
        if command == "load-uri":
            self._browser.load_url(args[0])

    def _title_changed_cb(self, embed, pspec):
        self.set_title(embed.props.title)

def start():
    if not _sugar.browser_startup(env.get_profile_path(), 'gecko'):
        raise "Error when initializising the web activity."

    style.load_stylesheet(stylesheet)
    
    download_manager = _sugar.get_download_manager()
    download_manager.connect('download-started', download_started_cb)
    download_manager.connect('download-completed', download_completed_cb)
    download_manager.connect('download-cancelled', download_started_cb)
    download_manager.connect('download-progress', download_progress_cb)

def stop():
    _sugar.browser_shutdown()

def download_started_cb(download_manager, download):
    name = download.get_url().rsplit('/', 1)[1]
    object_id = download.get_file_name() # The file name passed is already unique.

    cb_service = clipboardservice.get_instance()
    cb_service.add_object(object_id, name)
    cb_service.add_object_format(object_id,
                                 download.get_mime_type(),
                                 download.get_file_name(),
                                 on_disk = True)

def download_completed_cb(download_manager, download):
    cb_service = clipboardservice.get_instance()
    cb_service.set_object_percent(download.get_file_name(), 100)

def download_cancelled_cb(download_manager, download):
    #FIXME: Needs to update the state of the object to 'download stopped'.
    #FIXME: Will do it when we complete progress on the definition of the
    #FIXME: clipboard API.
    raise "Cancelling downloads still not implemented."

def download_progress_cb(download_manager, download):
    cb_service = clipboardservice.get_instance()
    cb_service.set_object_percent(download.get_file_name(), download.get_percent())
