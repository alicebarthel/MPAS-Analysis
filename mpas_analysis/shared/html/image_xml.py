import os
import sys
import shutil
import socket
import subprocess
import datetime
from lxml import etree
from PIL import Image

from ..io.utility import build_config_full_path


def write_image_xml(config, filePrefix, componentName, componentSubdirectory,
                    galleryGroup, groupLink, groupSubtitle=None, gallery=None,
                    thumbnailDescription='', imageDescription='',
                    imageCaption='', history=None, **kwargs):
    """
    Create an xml file describing the give plot, used to create a webpage
    including that plot and also to store provenance.  Also copies the image
    to the html subdirectory and generates thumbnails.

    Parameters
    ----------
    config : ``MpasAnalysisConfigParser`` object
        contains config options

    filePrefix : str
        the prefix (without base path or extension) of the input PNG image and
        the output XML file.

    componentName : {'Ocean', 'Sea Ice'}
        the name of the component this analysis belongs to.

    componentSubdirectory : {'ocean', 'sea_ice'}
        the name of the subdirectory where the component page and images will
        be stored.

    galleryGroup : str
        the name of the group of analysis galleries to which this analysis
        belongs

    groupLink : str
        the link within the html page used to identify the gallery group

    groupSubtitle : str, optional
        a subtitle for the gallery group (e.g. the observations being compared
        against or the season being plotted)

    gallery : str, optional
        the name of the gallery (or possibly a subtitle for the gallery group
        if there is only one gallery in the group)

    thumbnailDescription : str, optional
        a short description of the plot to be displayed under the thumbnail
        in the gallery

    imageDescription : str, optional
        a short description of the plot to be displayed as "alt" text if the
        image doesn't load or as a mouse-over

    imageCaption : str, optional
        a longer description of the plot to display when the image is full
        screen.  To force a linebreak, use ``<br>``

    history : str, optional
        A string providing command-line history of the data used to produce
        this plot.  The current command-line is prepended as part of adding
        provenance

    kwargs : dict
        additional keyword arguments will be used to add additional xml tags
        with the associated values

    Authors
    -------
    Xylar Asay-Davis
    """
    imageFileName = '{}.png'.format(filePrefix)
    plotsDirectory = build_config_full_path(config, 'output',
                                            'plotsSubdirectory')
    xmlFileName = '{}/{}.xml'.format(plotsDirectory, filePrefix)

    root = etree.Element("data")

    etree.SubElement(root, "imageFileName").text = imageFileName

    etree.SubElement(root, "componentName").text = componentName
    etree.SubElement(root, "componentSubdirectory").text = \
        componentSubdirectory

    etree.SubElement(root, "galleryGroup").text = galleryGroup
    if groupSubtitle is not None:
        etree.SubElement(root, "groupSubtitle").text = groupSubtitle
    etree.SubElement(root, "groupLink").text = groupLink

    if gallery is not None:
        etree.SubElement(root, "gallery").text = gallery

    etree.SubElement(root, "thumbnailDescription").text = \
        thumbnailDescription
    etree.SubElement(root, "imageDescription").text = \
        imageDescription
    etree.SubElement(root, "imageCaption").text = imageCaption

    generateHTML = config.getboolean('html', 'generate')
    if generateHTML:
        htmlBaseDirectory = build_config_full_path(config, 'output',
                                                   'htmlSubdirectory')
        componentDirectory = '{}/{}'.format(htmlBaseDirectory,
                                            componentSubdirectory)
        try:
            os.makedirs('{}/thumbnails'.format(componentDirectory))
        except OSError:
            pass

        plotsDirectory = build_config_full_path(config, 'output',
                                                'plotsSubdirectory')
        shutil.copyfile('{}/{}'.format(plotsDirectory, imageFileName),
                        '{}/{}'.format(componentDirectory, imageFileName))

        imageSize, orientation = _generate_thumbnails(imageFileName,
                                                      componentDirectory)

        etree.SubElement(root, "imageSize").text = \
            '{}x{}'.format(imageSize[0], imageSize[1])
        etree.SubElement(root, "orientation").text = orientation

    _provenance_command(root, history)

    for key, value in kwargs.items():
        etree.SubElement(root, key).text = str(value)

    tree = etree.ElementTree(root)
    tree.write(xmlFileName, xml_declaration=True, pretty_print=True)


def _provenance_command(root, history):  # {{{
    """
    Utility funciton for provenance of xml file associated with a plot.

    Authors
    -------
    Xylar Asay-Davis
    """
    call = ' '.join(sys.argv)
    if history is None:
        history = call
    else:
        # prepend the current provenance to the history being passed in
        history = call + '; ' + history
    etree.SubElement(root, 'history').text = history

    etree.SubElement(root, 'cwd').text = os.getcwd()
    etree.SubElement(root, 'user').text = os.getenv('USER')
    etree.SubElement(root, 'curtime').text = \
        datetime.datetime.now().strftime('%m/%d/%y %H:%M')

    etree.SubElement(root, 'host').text = socket.gethostname()

    p = subprocess.Popen(['git', 'describe', '--always', '--dirty'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.returncode == 0:
        githash = stdout.strip('\n')
    else:
        githash = 'git hash unavailable'

    etree.SubElement(root, 'githash').text = githash  # }}}


def _generate_thumbnails(imageFileName, directory):
    """
    Generate 2 thumbnails for the given image, one with the same aspect ratio
    and one with a fixed size. Note: The sizes are hard-coded to be consistent
    with the css template.  (They are displayed at 2/3 full size.)
    """
    # thumbnails with fixed size
    fixedWidth = 480
    fixedHeight = 360

    image = Image.open('{}/{}'.format(directory, imageFileName))
    thumbnailDir = '{}/thumbnails'.format(directory)

    imageSize = image.size

    if imageSize[0] < imageSize[1]:
        orientation = 'vert'
        thumbnailHeight = 480
    else:
        orientation = 'horiz'
        thumbnailHeight = 180

    # first, make a thumbnail with the same aspect ratio
    factor = image.size[1]/float(thumbnailHeight)
    size = [int(dim/factor + 0.5) for dim in image.size]
    thumbnail = image.resize(size, Image.ANTIALIAS)
    thumbnail.save('{}/{}'.format(thumbnailDir, imageFileName))

    # second, make a thumbnail with a fixed size
    widthFactor = image.size[0]/float(fixedWidth)
    heightFactor = image.size[1]/float(fixedHeight)

    factor = min(widthFactor, heightFactor)
    size = [int(dim/factor + 0.5) for dim in image.size]
    thumbnail = image.resize(size, Image.ANTIALIAS)

    if widthFactor <= heightFactor:
        # crop out the top of the thumbnail
        thumbnail = thumbnail.crop([0, 0, fixedWidth, fixedHeight])
    else:
        # # crop out the center of the thumbnail
        # left = int(0.5*(thumbnail.size[0] - fixedWidth) + 0.5)
        # thumbnail = thumbnail.crop([left, 0, left+fixedWidth, fixedHeight])

        # crop out the left side of the thubnail
        thumbnail = thumbnail.crop([0, 0, fixedWidth, fixedHeight])

    thumbnail.save('{}/fixed_{}'.format(thumbnailDir, imageFileName))

    return imageSize, orientation


# vim: foldmethod=marker ai ts=4 sts=4 et sw=4 ft=python
