import datetime
import logging
import re
from time import sleep
from types import SimpleNamespace
import unicodedata
import xml.etree.ElementTree as ET

import requests


CGPJ_APPOINTMENTS = "./" \
                    "/diario" \
                    "/seccion[@num='2A']" \
                    "/departamento[@nombre='CONSEJO GENERAL DEL PODER JUDICIAL']" \
                    "/epigrafe[@nombre='Nombramientos']" \
                    "/item"


def parse_date(text):
    DATE_PATTERN = re.compile(r'(?P<day>\d\d?) de (?P<month>\w+) de (?P<year>\d\d\d\d)')
    TO_MONTH_NUMBER = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}
    match = DATE_PATTERN.search(text)
    if match:
        date = match.groupdict()
        date['month'] = TO_MONTH_NUMBER[date['month']]
        date = datetime.date(int(date['year']), date['month'], int(date['day']))
    else:
        date = None
    return date

# DONE
# 2019-04-06
# chamber='Sala de lo Civil y Penal del Tribunal Superior de Justicia', court='Comunidad Valenciana'
PATTERNS = [
    # Real Decreto 368/2019, de 31 de mayo, por el que se nombra Magistrado de la Sala Primera del Tribunal Supremo a don José Luis Seoane Spiegelberg.
    re.compile(r'Real Decreto .+ nombra (?P<position>President.|Magistrad.) (?:del|de la) (?:(?P<chamber>Sala .+?) (?:del|de la) )?(?P<court>[^,]+)(?: correspondiente[^,]+)??(?:,.+)? a do(?:n|ña) (?P<person>.+)\.'),
    # Real Decreto 369/2019, de 31 de mayo, por el que se nombra a doña Adoración María Riera Ocariz, Magistrada de la Sala de lo Penal de la Audiencia Nacional.
    # Real Decreto 899/2018, de 13 de julio, por el que se nombra a don Javier María Calderón González, Magistrado de la Audiencia Provincial de Madrid correspondiente al orden penal.
    re.compile(r'Real Decreto .+ nombra a do(?:n|ña) (?P<person>.+), (?P<position>President.|Magistrad.) (?:del|de la) (?:(?P<chamber>Sala .+?) (?:del|de la) )?(?P<court>[^,]+?)(?: correspondiente[^,]+)?(?:,.+)?\.'),
]
# TODO:
# Corrección de errores del Real Decreto 462/2019, de 26 de julio, por el que se nombra Presidente de la Audiencia Provincial de Zamora a don Jesús Pérez Serna.
# Real Decreto 358/2019, de 24 de mayo, por el que, en ejecución de la Sentencia de 3 de abril de 2019, de la Sección Sexta de la Sala Tercera del Tribunal Supremo, en relación con el recurso contencioso-administrativo n.º 480/2017, se deja sin efecto el nombramiento del Magistrado don Eloy Velasco Núñez.
# Real Decreto 361/2019, de 24 de mayo, por el que, en ejecución de la Sentencia de 3 de abril de 2019, de la Sección Sexta de la Sala Tercera del Tribunal Supremo, en relación con el recurso contencioso-administrativo n.º 480/2017, se nombra a don Ángel Luis Hurtado Adrián, Magistrado de la Sala de Apelación de la Audiencia Nacional.
# Acuerdo de 28 de marzo de 2019, del Pleno del Consejo General del Poder Judicial, por el que se nombra Secretario General del Consejo a don José Luis de Benito y Benítez de Lugo.
# Acuerdo de 28 de marzo de 2019, del Pleno del Consejo General del Poder Judicial, por el que se nombra Vicesecretario General del Consejo a don Gervasio Martín Martín.
# Real Decreto 62/2019, de 8 de febrero, por el que se nombra en propiedad a don José Ignacio López Cárcamo, Magistrado de la Sala de lo Contencioso-Administrativo del Tribunal Superior de Justicia de Cantabria.

# Situaciones
PATTERNS2 = [
# Acuerdo de 30 de abril de 2019, de la Comisión Permanente del Consejo General del Poder Judicial, por el que se declara la jubilación forzosa del Magistrado don Alberto Gumersindo Jorge Barreiro, al cumplir la edad legalmente establecida.
# Acuerdo de 11 de julio de 2019, de la Comisión Permanente del Consejo General del Poder Judicial, por el que se declara la jubilación voluntaria anticipada de la Magistrada doña María Pilar Martín Coscolla.
    re.compile(r'Acuerdo .+ jubilación .+ Magistrad. do(?:n|ña) (?P<person>[^.,]+).+'),
]


logger = logging.getLogger(__name__)


class Appointment(SimpleNamespace):
    pass


class Situation(SimpleNamespace):
    pass


class Cessation(SimpleNamespace):
    pass


class Item(SimpleNamespace):
    pass


class Boe:
    BASE_URL = 'http://boe.es'
    # summary_url = base_url + '/diario_boe/xml.php?id=BOE-S-{date:%Y}{date:%m}{date:%D}'
    XML_URL = BASE_URL + '/diario_boe/xml.php?id={id}'
    ITEMS = {
        'root': './/diario',
        'section': 'seccion',
        'department': 'departamento',
        'epigraph': 'epigrafe',
        'item': 'item'
    }

    @staticmethod
    def get_doc(id=None, retry=True, secs=1):
        if not id:
            return
        while retry:
            try:
                sleep(secs)
                request = requests.get(Boe.XML_URL.format(id=id))
            except requests.exceptions.SSLError:
                secs += 1
            else:
                retry = False
        if not request.ok:
            logger.error(f"Request: XML request is not OK for URL: {Boe.XML_URL.format(id=id)}")
            return
        text = request.text
        # print(text0)
        # text = unicodedata.normalize('NFKD', request.text)  # 2019-10-26: día\xa027 de octubre de\xa02019
        # print(text)
        doc = ET.fromstring(text)
        return doc

    @staticmethod
    def get_summary(date=None):
        if not date:
            date = datetime.datetime.today().date()
        id = 'BOE-S-{date:%Y}{date:%m}{date:%d}'.format(date=date)
        summary = Boe.get_doc(id=id)
        return summary

    @staticmethod
    def list_items(summary, section=None, department=None, epigraph=None):
        xpath = []
        for key, value in Boe.ITEMS.items():
            if key == 'section' and section:
                value += f"[@num='{section}']"
                ignore_epigraph = int(section[0]) >= 4
            elif key == 'department' and department:
                value += f"[@nombre='{department.upper()}']"
            elif key == 'epigraph':
                if ignore_epigraph:
                    value = None
                elif epigraph:
                    value += f"[@nombre='{epigraph}']"
            if value:
                xpath.append(value)
        xpath = '/'.join(xpath)
        nodes = summary.findall(xpath)
        items = []
        for node in nodes:
            id = node.attrib['id']
            title = node.find('titulo').text
            url_htm = node.find('urlHtm').text
            url_xml = node.find('urlXml').text
            items.append(Item(id=id, title=title, url_htm=url_htm, url_xml=url_xml))
        return items


class SpecificParser:
    @staticmethod
    def _list_items(summary):
        items = Boe.list_items(summary, section='2A', department='CONSEJO GENERAL DEL PODER JUDICIAL',
                               epigraph='Nombramientos')
        return items

    @staticmethod
    def _parse(items):#, items=None):
        # if not items:
        #     items = self.list_cgpj_appointments()
        appointments = []
        for item in items:
            for pattern in PATTERNS:
                match = pattern.match(item.title)
                if match:
                    kwargs = match.groupdict()
                    # Get date
                    doc = Boe.get_doc(id=item.id)
                    date = doc.find('.//fecha_disposicion').text
                    date = datetime.datetime.strptime(date, '%Y%m%d').date()
                    #
                    # for child in doc:
                    #     print(child.tag, child.attrib)
                    # text = doc.find('.//texto')
                    # for p in text:
                    #     print(p.text)
                    paragraph = doc.find('.//texto/p[2]').text
                    print()
                    print(item.title)
                    print(paragraph)
                    print()
                    # Append Appointment
                    appointments.append(Appointment(id=item.id, date=date, **kwargs))
                    break
            if not match:
                logger.error(f"Parsing for title = '{item.title}'")
        return appointments

    @staticmethod
    def parse(summary):
        items = SpecificParser._list_items(summary)
        items = SpecificParser._parse(items)
        return items


class Specific2Parser:
    @staticmethod
    def _list_items(summary):
        items = Boe.list_items(summary, section='2A', department='CONSEJO GENERAL DEL PODER JUDICIAL',
                               epigraph='Situaciones')
        return items

    @staticmethod
    def _parse(items):#, items=None):
        # if not items:
        #     items = self.list_cgpj_appointments()
        appointments = []
        for item in items:
            for pattern in PATTERNS2:
                match = pattern.match(item.title)
                if match:
                    kwargs = match.groupdict()
                    # Get date
                    doc = Boe.get_doc(id=item.id)
                    # date = doc.find('.//fecha_publicacion').text
                    # date = datetime.datetime.strptime(date, '%Y%m%d').date()
                    #
                    # for child in doc:
                    #     print(child.tag, child.attrib)
                    # text = doc.find('.//texto')
                    # for p in text:
                    #     print(p.text)
                    paragraph = unicodedata.normalize('NFKD', doc.find('.//texto/p[2]').text)  # 2019-10-26: día\xa027 de octubre de\xa02019
                    # paragraph = doc.find('.//texto/p[2]').text
                    print()
                    print(item.tile)
                    print(paragraph)
                    print()
                    date = parse_date(paragraph)
                    # Append Appointment
                    appointments.append(Situation(id=item.id, date=date, **kwargs))
                    break
            if not match:
                logger.error(f"Parsing for title = '{item.title}'")
        return appointments

    @staticmethod
    def parse(summary):
        items = Specific2Parser._list_items(summary)
        items = Specific2Parser._parse(items)
        return items
