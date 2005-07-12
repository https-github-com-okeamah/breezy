# Copyright (C) 2005 by Canonical Ltd

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from trace import mutter
from bzrlib.store import Store, CompressedTextStore
from bzrlib.local_transport import LocalTransport

try:
    set
except NameError:
    from sets import Set as set

class CachedStore(Store):
    """A store that caches data locally, to avoid repeated downloads.
    The precacache method should be used to avoid server round-trips for
    every piece of data.
    """
    def __init__(self, store, cache_dir):
        self.source_store = store
        self.cache_store = CompressedTextStore(LocalTransport(cache_dir))

    def __getitem__(self, id):
        mutter("Cache add %s" % id)
        if id not in self.cache_store:
            self.cache_store.add(id, self.source_store[id])
        return self.cache_store[id]

    def __contains__(self, fileid):
        if fileid in self.cache_store:
            return True
        if fileid in self.source_store:
            # We could copy at this time
            return True
        return False

    def get(self, fileids):
        fileids = list(fileids)
        hasids = self.cache_store.has(fileids)
        needs = set()
        for has, fileid in zip(hasids, fileids):
            if not has:
                needs.add(fileid)
        if needs:
            self.cache_store.copy_multi(self.source_store, needs)
        return self.cache_store.get(fileids)

    def prefetch(self, ids):
        """Copy a series of ids into the cache, before they are used.
        For remote stores that support pipelining or async downloads, this can
        increase speed considerably.
        """
        mutter("Prefetch of ids %s" % ",".join(ids))
        self.cache_store.copy_multi(self.source_store, ids)
