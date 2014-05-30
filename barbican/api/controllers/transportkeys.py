# Copyright (c) 2014 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import urllib

import pecan

from barbican import api
from barbican.api import controllers as con
from barbican.api.controllers import hrefs
from barbican.common import exception
from barbican.common import utils
from barbican.common import validators
from barbican.model import models
from barbican.model import repositories as repo
from barbican.openstack.common import gettextutils as u

LOG = utils.getLogger(__name__)


def _transport_key_not_found():
    """Throw exception indicating transport key not found."""
    pecan.abort(404, u._('Not Found. Transport Key not found.'))


class TransportKeyController(object):
    """Handles transport key retrieval requests."""

    def __init__(self, transport_key_id, transport_key_repo=None):
        LOG.debug('=== Creating TransportKeyController ===')
        self.transport_key_id = transport_key_id
        self.repo = transport_key_repo or repo.TransportKeyRepo()

    @pecan.expose(generic=True)
    @con.handle_exceptions(u._('Transport Key retrieval'))
    @con.handle_rbac('transport_key:get')
    def index(self, keystone_id):
        LOG.debug("== Getting transport key for %s" % keystone_id)
        transport_key = self.repo.get(entity_id=self.transport_key_id)
        if not transport_key:
            _transport_key_not_found()

        pecan.override_template('json', 'application/json')
        return transport_key

    @index.when(method='DELETE')
    @con.handle_exceptions(u._('Transport Key deletion'))
    @con.handle_rbac('transport_key:delete')
    def on_delete(self, keystone_id):
        LOG.debug("== Deleting transport key ===")
        try:
            self.repo.delete_entity_by_id(entity_id=self.transport_key_id,
                                          keystone_id=keystone_id)
            # TODO(alee) response should be 204 on success
            # pecan.response.status = 204
        except exception.NotFound:
            LOG.exception('Problem deleting transport_key')
            _transport_key_not_found()


class TransportKeysController(object):
    """Handles transport key list requests."""

    def __init__(self, transport_key_repo=None):
        LOG.debug('Creating TransportKeyController')
        self.repo = transport_key_repo or repo.TransportKeyRepo()
        self.validator = validators.NewTransportKeyValidator()

    @pecan.expose()
    def _lookup(self, transport_key_id, *remainder):
        return TransportKeyController(transport_key_id, self.repo), remainder

    @pecan.expose(generic=True, template='json')
    @con.handle_exceptions(u._('Transport Key(s) retrieval'))
    @con.handle_rbac('transport_keys:get')
    def index(self, keystone_id, **kw):
        LOG.debug('Start transport_keys on_get')

        plugin_name = kw.get('plugin_name', None)
        if plugin_name is not None:
            plugin_name = urllib.unquote_plus(plugin_name)

        result = self.repo.get_by_create_date(
            plugin_name=plugin_name,
            offset_arg=kw.get('offset', 0),
            limit_arg=kw.get('limit', None),
            suppress_exception=True
        )

        transport_keys, offset, limit, total = result

        if not transport_keys:
            transport_keys_resp_overall = {'transport_keys': [],
                                           'total': total}
        else:
            transport_keys_resp = [
                hrefs.convert_transport_key_to_href(keystone_id, s.id)
                for s in transport_keys
            ]
            transport_keys_resp_overall = hrefs.add_nav_hrefs(
                'transport_keys', keystone_id, offset, limit, total,
                {'transport_keys': transport_keys_resp}
            )
            transport_keys_resp_overall.update({'total': total})

        return transport_keys_resp_overall

    @index.when(method='POST', template='json')
    @con.handle_exceptions(u._('Transport Key Creation'))
    @con.handle_rbac('transport_keys:post')
    def on_post(self, keystone_id):
        LOG.debug('Start transport_keys on_post')

        # TODO(alee) POST should determine the plugin name and call the
        # relevant get_transport_key() call.  We will implement this once
        # we figure out how the plugins will be enumerated.

        data = api.load_body(pecan.request, validator=self.validator)

        new_key = models.TransportKey(data.get('plugin_name'),
                                      data.get('transport_key'))

        self.repo.create_from(new_key)

        pecan.response.status = 201
        pecan.response.headers['Location'] = '/{0}/transport_keys/{1}'.format(
            keystone_id, new_key.id
        )
        url = hrefs.convert_transport_key_to_href(keystone_id, new_key.id)
        LOG.debug('URI to transport key is {0}'.format(url))
        return {'transport_key_ref': url}