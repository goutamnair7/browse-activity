#
#    Copyright (C) 2007, One Laptop Per Child
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import logging
import os
import dbus
from dbus.gobject_service import ExportedGObject
import base64
import sha

SERVICE = "org.laptop.WebActivity"
IFACE = SERVICE
PATH = "/org/laptop/WebActivity"

_logger = logging.getLogger('messenger')

class Messenger(ExportedGObject):
    def __init__(self, tube, is_initiator, model, linkbar, owner):
        ExportedGObject.__init__(self, tube, PATH)
        self.tube = tube
        self.is_initiator = is_initiator
        self.members = []
        self.entered = False
        self.linkbar = linkbar
        self.model = model
        self.owner = owner
        _logger.debug('Owner=%s %s' %(self.owner.props.nick, self.owner.props.color))
        self.tube.watch_participants(self.participant_change_cb)
    
    def participant_change_cb(self, added, removed):
        for handle in removed:
            _logger.debug('Member %s left' %(self.tube.participants[handle]))
            if self.tube.participants[handle] == self.members[0]:
                # TOFIX: the creator leaves the activity, name a new leader
                _logger.debug('The creator leaves.')
                # if self.id == 1:
                #    _logger.debug('I become the new leader.')
                #    self.is_initiator = True                
            try:
                self.members.remove(self.tube.participants[handle])
            except ValueError:
                # already absent
                pass

        if not self.entered:
            self.tube.add_signal_receiver(self._add_link_receiver, '_add_link', IFACE, path=PATH, sender_keyword='sender',
                                           byte_arrays=True)
            self.tube.add_signal_receiver(self._rm_link_receiver, '_rm_link', IFACE, path=PATH, sender_keyword='sender',
                                           byte_arrays=True)
            self.tube.add_signal_receiver(self._hello_receiver, '_hello_signal', IFACE, path=PATH, sender_keyword='sender')
            if self.is_initiator:
                _logger.debug('Initialising a new shared browser, I am %s .'%self.tube.get_unique_name())
                self.id = self.tube.get_unique_name()
                self.members = [self.id]
            else:               
                self._hello_signal()
        self.entered = True
        
    @dbus.service.signal(IFACE, signature='')
    def _hello_signal(self):
        '''Notify current members that you joined '''
        _logger.debug('Sending hello to all')
    
    def _hello_receiver(self, sender=None):
        '''A new member joined the activity, sync linkbar'''
        self.members.append(sender)            
        if self.is_initiator:
            self.tube.get_object(sender, PATH).init_members(self.members)            
            for link in self.model.links:
                if link['deleted'] == 0:
                    self.tube.get_object(sender, PATH).transfer_links(link['url'], link['title'], link['color'], link['owner'], base64.b64encode(link['thumb']),dbus_interface=IFACE, reply_handler=self.reply_transfer, error_handler=lambda e:self.error_transfer(e, 'transfering file'))

    def reply_transfer(self):
        pass
            
    def error_transfer(self, e, when):    
        _logger.error('Error %s: %s'%(when, e))

    @dbus.service.method(dbus_interface=IFACE, in_signature='as', out_signature='')
    def init_members(self, members):
        '''Sync the list of members '''
        _logger.debug('Data received to sync member list.')
        self.members = members
        self.id = self.members.index(self.tube.get_unique_name())
        
    @dbus.service.method(dbus_interface=IFACE, in_signature='sssss', out_signature='')
    def transfer_links(self, url, title, color, owner, buffer):
        '''Sync the link list with the others '''
        _logger.debug('Data received to sync link list.')
        thumb = base64.b64decode(buffer)
        self.model.links.append( {'hash':sha.new(url).hexdigest(), 'url':url, 'title':title, 'thumb':thumb,
                                  'owner':owner, 'color':color, 'deleted':0} )            
        self.linkbar._add_link(url, thumb, color, title, owner, len(self.model.links)-1)
            
    def add_link(self, url, title, color, owner, thumb):
        _logger.debug('Add Link: %s '%url)
        self._add_link(url, title, color, owner, base64.b64encode(thumb))
        
    @dbus.service.signal(IFACE, signature='sssss')
    def _add_link(self, url, title, color, owner, thumb):        
        '''Signal to send the link information (add)'''
        
    def _add_link_receiver(self, url, title, color, owner, thumb, sender=None):
        '''Member sent a link'''
        handle = self.tube.bus_name_to_handle[sender]            
        if self.tube.self_handle != handle:
            buffer = base64.b64decode(thumb)

            self.model.links.append( {'hash':sha.new(url).hexdigest(), 'url':url, 'title':title, 'thumb':buffer,
                                      'owner':owner, 'color':color, 'deleted':0} )            
            self.linkbar._add_link(url, buffer, color, title, owner, len(self.model.links)-1)                
            _logger.debug('Added link: %s to linkbar.'%(url))
    
    def rm_link(self, linkname):
        _logger.debug('Remove Link: %s '%linkname)
        self._rm_link(linkname)
        
    @dbus.service.signal(IFACE, signature='s')
    def _rm_link(self, linkname):        
        '''Signal to send the link information (rm)'''
        
    def _rm_link_receiver(self, linkname, sender=None):
        '''Member sent signal to remove a link'''
        handle = self.tube.bus_name_to_handle[sender]            
        if self.tube.self_handle != handle:
            self.linkbar._rm_link_messenger(linkname)
            _logger.debug('Removed link: %s from linkbar.'%(linkname))
        
