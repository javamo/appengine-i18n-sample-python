#!/usr/bin/env python
#
# Copyright 2013 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A small module for i18n of webapp2 and jinja2 based apps.

The idea of this example, especially for how to translate strings in
Javascript is originally from an implementation of Django i18n.
"""


import gettext
import os

import webapp2
from webob.acceptparse import AcceptLanguage


def convert_translations_to_dict(js_translations):
    """Convert a GNUTranslation object into a dict for jsonifying."""

    plural = None
    n_plural = 2
    if '' in js_translations._catalog:
        for l in js_translations._catalog[''].split('\n'):
            if l.startswith('Plural-Forms:'):
                plural = l.split(':', 1)[1].strip()
    if plural is not None:
        for element in [raw_elm.strip() for raw_elm in plural.split(';')]:
            if element.startswith('nplurals='):
                n_plural = int(element.split('=', 1)[1])
            elif element.startswith('plural='):
                plural = element.split('=', 1)[1]
    else:
        n_plural = 2
        plural = '(n == 1) ? 0 : 1'

    translations_dict = {'plural': plural, 'catalog': {}, 'fallback': None}
    if js_translations._fallback is not None:
        translations_dict['fallback'] = convert_translations_to_dict(
              js_translations._fallback
        )
    for key, value in js_translations._catalog.items():
        if key == '':
            continue
        if type(key) in (str, unicode):
            translations_dict['catalog'][key] = value
        elif type(key) == tuple:
            if not key[0] in translations_dict['catalog']:
                translations_dict['catalog'][key[0]] = [''] * n_plural
            translations_dict['catalog'][key[0]][int(key[1])] = value
    return translations_dict


class BaseHandler(webapp2.RequestHandler):
    """A base handler for installing i18n-aware Jinja2 environment."""

    @webapp2.cached_property
    def jinja2_env(self):
        """Cached property for a Jinja2 environment."""

        import jinja2

        jinja2_env = jinja2.Environment(
              loader=jinja2.FileSystemLoader(
                    os.path.join(os.path.dirname(__file__), 'templates')),
              extensions=['jinja2.ext.i18n'])
        jinja2_env.install_gettext_translations(
              self.request.environ['active_translation'])
        jinja2_env.globals['get_i18n_js_tag'] = self.get_i18n_js_tag
        return jinja2_env

    def get_i18n_js_tag(self):
        """Generates a Javascript tag for i18n in Javascript."""

        template = self.jinja2_env.get_template('javascript_tag.jinja2')
        return template.render({'javascript_body': self.get_i18n_js()})

    def get_i18n_js(self):
        """Generates a Javascript body for i18n in Javascript."""

        import json

        try:
            js_translations = gettext.translation(
                  'jsmessages', 'locales', fallback=False,
                  languages=self.request.environ['preferred_languages'],
                  codeset='utf-8')
        except IOError:
            template = self.jinja2_env.get_template('null_i18n_js.jinja2')
            return template.render()

        translations_dict = convert_translations_to_dict(js_translations)
        template = self.jinja2_env.get_template('i18n_js.jinja2')
        return template.render(
              {'translations': json.dumps(translations_dict, indent=1)})


class I18nMiddleware(object):
    """A middleware for determining users' preferred language."""

    def __init__(self, app, default_language='en', locale_path=None):
        """A constructor for this middleware.

        Args:
          app: A WSGI app that you want to wrap with this middleware.
          default_language: fallback language; ex: 'en', 'pl' or 'ja'
          locale_path: A directory containing the translations file.
                       (defaults to 'locales' directory)
        """

        self.app = app
        if locale_path is None:
            locale_path = os.path.join(
                  os.path.abspath(os.path.dirname(__file__)), 'locales')
        self.locale_path = locale_path
        self.default_language = default_language

    def __call__(self, environ, start_response):
        accept_language = AcceptLanguage(
              environ.get("HTTP_ACCEPT_LANGUAGE", self.default_language))
        preferred_languages = accept_language.best_matches()
        if not self.default_language in preferred_languages:
            preferred_languages.append(self.default_language)
        translation = gettext.translation(
              'messages', self.locale_path, fallback=True,
              languages=preferred_languages, codeset='utf-8')
        translation.install(unicode=True, names=['gettext', 'ngettext'])
        environ['active_translation'] = translation
        environ['preferred_languages'] = preferred_languages

        return self.app(environ, start_response)
