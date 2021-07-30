# Copyright (c) 2021, DjaoDjin inc.
#   All rights reserved.

import glob, logging, os, subprocess

from django.conf import settings
from django.utils._os import safe_join
from django.views.generic import View
#from django.views.static import serve as django_static_serve
from django.contrib.staticfiles.views import serve as django_static_serve

from .. import settings
from ..helpers import get_assets_dirs

LOGGER = logging.getLogger(__name__)


class AssetView(View):
    """
    If you are using django.contrib.staticfiles, you will need to use
    the --nostatic command to disable the runserver-installed bypass
    for static files.
    """
    source_root = None
    assets_map = None

    def get(self, request, *args, **kwargs):
        assets_map = self.assets_map if self.assets_map else settings.ASSETS_MAP
        rel_path = self.kwargs.get('path')

        source = assets_map.get(rel_path)
        LOGGER.debug("checks if %s needs to be rebuilt from sources %s",
            rel_path, source)
        if source:
            cache_root = None
            source_root = self.source_root
            if not source_root:
                source_root = settings.ASSETS_SOURCES_DIR
            for base_path in get_assets_dirs():
                cache_name = safe_join(base_path, rel_path)

                LOGGER.debug(
                    "compare timestamps of cache file %s to sources in %s",
                    cache_name, source_root)
                try:
                    statinfo = os.stat(cache_name)
                    cache_mtime = statinfo.st_mtime
                    rebuild = False
                    src_pats = source[1]
                    for src_pat in src_pats:
                        for src_name in glob.iglob(safe_join(
                                source_root, src_pat)):
                            statinfo = os.stat(src_name)
                            LOGGER.debug("   %s: %s > %s ? %s",
                                src_name, statinfo.st_mtime, cache_mtime,
                                statinfo.st_mtime > cache_mtime)
                            if statinfo.st_mtime > cache_mtime:
                                rebuild = True
                                break
                        if rebuild:
                            break
                    cache_root = base_path
                    break
                except FileNotFoundError:
                    # If we cannot find the file, then let's continue,
                    # maybe it is present in another assets directory.
                    LOGGER.debug("cannot stat(%s)", str(cache_name))

            if not cache_root or rebuild:
                LOGGER.debug("rebuild %s", str(rel_path))
                if not cache_root:
                    cache_root = get_assets_dirs()[0]
                scss_filename = safe_join(source_root, source[0])
                css_filename = safe_join(cache_root, rel_path)
                cmd = [settings.SASSC_BIN, scss_filename, css_filename]
                LOGGER.info("RUN: %s", ' '.join(cmd))
                try:
                    subprocess.check_output(cmd)
                except subprocess.CalledProcessError as err:
                    LOGGER.error("%s" % str(err))
                    os.remove(css_filename)
                    assert not os.path.exists(css_filename)
            else:
                LOGGER.debug("no rebuild of %s", str(rel_path))

        resp = django_static_serve(request, rel_path)
        if source:
            resp['Cache-Control'] = 'no-cache'
        return resp
