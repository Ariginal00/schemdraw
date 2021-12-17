''' Schemdraw base Element class '''

from __future__ import annotations
from typing import Sequence, MutableMapping, Any, Union
from collections import ChainMap
from dataclasses import dataclass
import warnings
import math

from ..segments import Segment, SegmentPoly, SegmentText, SegmentCircle, SegmentArc, BBox, SegmentType
from ..transform import Transform
from .. import util
from ..util import Point
from ..types import XY, Linestyle, Align, Halign, Valign, LabelLoc

gap = (math.nan, math.nan)  # Put a gap in a path

Figure = None
def _set_elm_backend(figureclass):
    global Figure
    Figure = figureclass


@dataclass
class Label:
    ''' Element Label Parameters. '''
    label: str | Sequence[str]
    loc: LabelLoc | None = None   # top, bot, lft, rgt, OR anchor
    ofst: XY | float | None = None
    align: Align | None = None
    rotate: bool | float = False  # True=same angle as element; False = 0
    fontsize: float | None = None
    font: str | None = None
    color: str | None = None


class Element:
    ''' Standard circuit element.

        Keyword Arguments are equivalent to calling
        setter methods.
        
        Args:
            d: Drawing direction ('up', 'down', 'left', 'right')

        Attributes:
            anchors: Dictionary of anchor positions in element
                coordinates
            absanchors: Dictionary of anchor positions in absolute
                drawing coordinates
            segments: List of drawing primitives making up the element
            transform: Transformation from element to drawing coordinates

        Anchor names are dynmically added as attributes after placing the
        element in a Drawing.
    '''
    def __init__(self, *d, **kwargs):
        self._userparams = kwargs                       # Specified by user
        self._dwgparams: MutableMapping[str, Any] = {}  # Defaults from drawing
        self.params: MutableMapping[str, Any] = {}      # Element-specific definition
        self._cparams: MutableMapping[str, Any] = {}    # ChainMap of above params
        self._localshift: XY = Point((0, 0))
        self._userlabels: list[Label] = []

        self.anchors: MutableMapping[str, Union[Point, tuple[float,float]]] = {}     # Untransformed anchors
        self.absanchors: MutableMapping[str, Any] = {}  # Transformed, absolute anchors
        self.segments: list[SegmentType] = []
        self.transform = Transform(0, [0, 0])

        if 'xy' in self._userparams:  # Allow legacy 'xy' parameter
            self._userparams.setdefault('at', self._userparams.pop('xy'))
        if d:
            self._userparams['d'] = d[0]
            if len(d) > 1:
                warnings.warn('Unused positional arguments in Element.')

    def __getattr__(self, name: str) -> Any:
        ''' Allow getting anchor position as attribute '''
        if name in vars(self).get('absanchors', {}):
            return vars(self).get('absanchors')[name]  # type: ignore
        raise AttributeError(f'{name} not defined in Element')

    def up(self) -> 'Element':
        ''' Set the direction to up '''
        if 'd' in self._userparams:
            warnings.warn(f"Duplicated direction parameter in element. `{self._userparams['d']}` changed to `up`.")
        self._userparams['d'] = 'up'
        return self

    def down(self) -> 'Element':
        ''' Set the direction to down '''
        if 'd' in self._userparams:
            warnings.warn(f"Duplicated direction parameter in element. `{self._userparams['d']}` changed to `down`.")
        self._userparams['d'] = 'down'
        return self

    def left(self) -> 'Element':
        ''' Set the direction to left '''
        if 'd' in self._userparams:
            warnings.warn(f"Duplicated direction parameter in element. `{self._userparams['d']}` changed to `left`.")        
        self._userparams['d'] = 'left'
        return self

    def right(self) -> 'Element':
        ''' Set the direction to right '''
        if 'd' in self._userparams:
            warnings.warn(f"Duplicated direction parameter in element. `{self._userparams['d']}` changed to `right`.")        
        self._userparams['d'] = 'right'
        return self

    def theta(self, theta: float) -> 'Element':
        ''' Set the drawing direction angle in degrees '''
        if 'd' in self._userparams:
            warnings.warn(f"Duplicate direciton parameter in element: `{self._userparams['d']}` replaced with `theta={theta}`")
        self._userparams['theta'] = theta
        return self

    def at(self, xy: XY | tuple['Element', str]) -> 'Element':
        ''' Set the element xy position

            Args:
                xy: (x,y) position or tuple of (Element, anchorname)
        '''
        if 'at' in self._userparams:
            warnings.warn(f"Duplicate `at` parameter in element: `{self._userparams['at']}` changed to `{xy}`.")
        self._userparams['at'] = xy
        return self

    def scale(self, scale: float=1) -> 'Element':
        ''' Apply scale/zoom factor to element '''
        self._userparams['zoom'] = scale
        return self

    def flip(self)-> 'Element':
        ''' Apply flip up/down '''
        self._userparams['flip'] = True
        return self

    def reverse(self) -> 'Element':
        ''' Apply reverse left/right '''
        self._userparams['reverse'] = True
        return self

    def anchor(self, anchor: str) -> 'Element':
        ''' Specify anchor for placement. The anchor will be
            aligned with the position specified by `at()` method.
        '''
        if 'anchor' in self._userparams:
            warnings.warn(f"Duplicate anchor parameter in element: `{self._userparams['anchor']}` changed to `{anchor}`.")

        self._userparams['anchor'] = anchor
        return self

    def color(self, color: str) -> 'Element':
        ''' Sets the element color

            Args:
                color: color name or hex value (ie '#FFFFFF')
        '''
        self._userparams['color'] = color
        return self

    def linestyle(self, ls: Linestyle) -> 'Element':
        ''' Sets the element line style

            Args:
                ls: Line style ('-', ':', '--', '-.').
        '''
        self._userparams['ls'] = ls
        return self

    def linewidth(self, lw: float) -> 'Element':
        ''' Sets the element line width

            Args:
                lw: Line width
        '''
        self._userparams['lw'] = lw
        return self

    def fill(self, color: bool | str=True) -> 'Element':
        ''' Sets the element fill color.

            Args:
                color: Color string name or hex value, or
                `True` to fill with the element line color.
        '''
        self._userparams['fill'] = color
        return self

    def style(self, color: str=None, fill: str=None,
              ls: Linestyle=None, lw: float=None) -> 'Element':
        ''' Apply all style parameters

            Args:
                color: Color string or hex value
                fill: Color string or hex
                ls: Line style ('-', ':', '--', '-.')
                lw: Line width
        '''
        if color is not None:
            self.color(color)
        if fill is not None:
            self.fill(fill)
        if ls is not None:
            self.linestyle(ls)
        if lw is not None:
            self.linewidth(lw)
        return self

    def zorder(self, zorder: int) -> 'Element':
        ''' Sets the element zorder. Higher zorders will be drawn above
            lower zorder elements.
        '''
        self._userparams['zorder'] = zorder
        return self

    def hold(self) -> 'Element':
        ''' Do not move the Drawing `here` position after placing this element '''
        self._userparams['move_cur'] = False
        return self

    def label(self, label: str | Sequence[str],
              loc: LabelLoc=None,
              ofst: XY | float | None=None,
              halign: Halign=None,
              valign: Valign=None,
              rotate: bool | float=False,
              fontsize: float=None,
              font: str=None,
              color: str=None):
        ''' Add a label to the Element.

            Args:
                label: The text string or list of strings. If list, each string will
                    be evenly spaced along the element (e.g. ['-', 'V', '+'])
                loc: Label position within the Element. Either ('top', 'bottom', 'left',
                    'right'), or the name of an anchor within the Element.
                ofst: Offset from default label position
                halign: Horizontal text alignment ('center', 'left', 'right')
                valign: Vertical text alignment ('center', 'top', 'bottom')
                rotate: True to rotate label with element, or specify rotation
                    angle in degrees
                fontsize: Size of label font
                font: Name/font-family of label
                color: Color of label
        '''
        if halign is None and valign is None:
            align = None
        else:
            align = (halign, valign)
        if not rotate:
            rotate = 0
        elif isinstance(rotate, bool):
            rotate = True
        self._userlabels.append(Label(label, loc, ofst, align, rotate, fontsize, font, color))
        return self

    def _buildparams(self) -> None:
        ''' Combine parameters from user, setup, and drawing. Fills self._cparams '''
        # Accomodate xy positions based on OTHER elements before they are fully set up.
        if 'at' in self._userparams and isinstance(self._userparams['at'][1], str):
            element, pos = self._userparams['at']
            if pos in element.absanchors:
                xy = element.absanchors[pos]
            else:
                raise KeyError('Unknown anchor name {}'.format(pos))
            self._userparams['at'] = xy

        # All subsequent actions get params from cparams
        self._cparams = ChainMap(self._userparams, self.params, self._dwgparams)
        self._flipreverse()

    def _flipreverse(self) -> None:
        ''' Flip and/or reverse element's segments if necessary '''
        if self._userparams.get('flip', False):
            [s.doflip() for s in self.segments]  # type: ignore
            for name, pt in self.anchors.items():
                self.anchors[name] = Point(pt).flip()

        if self._userparams.get('reverse', False):
            if 'center' in self.anchors:
                centerx = self.anchors['center'][0]
            else:
                xmin, _, xmax, _ = self.get_bbox(includetext=False)
                centerx = (xmin + xmax)/2
            [s.doreverse(centerx) for s in self.segments]  # type: ignore
            for name, pt in self.anchors.items():
                self.anchors[name] = Point(pt).mirrorx(centerx)

    def _place(self, dwgxy: XY, dwgtheta: float, **dwgparams) -> tuple[Point, float]:
        ''' Calculate element position within the drawing '''
        self._dwgparams = dwgparams
        if not self._cparams:
            self._buildparams()

        anchor = self._cparams.get('anchor', None)
        zoom = self._cparams.get('zoom', 1)
        xy = self._cparams.get('at', dwgxy)

        # Get bounds of element, used for positioning user labels
        self.bbox = self.get_bbox(includetext=False)

        theta: float
        if 'endpts' in self._cparams:
            theta = dwgtheta
        elif self._cparams.get('d') is not None:
            d = self._cparams.get('d')
            if str(d).lstrip('-').isnumeric():
                theta = float(str(d))
            else:
                theta = {'u': 90, 'r': 0, 'l': 180, 'd': 270}[d[0].lower()]  # type: ignore
        else:
            theta = self._cparams.get('theta', dwgtheta)

        if anchor is not None:
            self._localshift = -Point(self.anchors[anchor])
        self.transform = Transform(theta, xy, self._localshift, zoom)

        # Add user-defined labels
        # user-defined labels - allow element def to define label location
        lblloc = self._cparams.get('lblloc', 'top')
        lblsize = self._cparams.get('lblsize', self._cparams.get('fontsize', 14))
        lblrotate = self._cparams.get('lblrotate', False)
        lblcolor = self._cparams.get('color', 'black')
        kwlabels = {
            'top': self._cparams.get('toplabel', None),
            'bot': self._cparams.get('botlabel', None),
            'lft': self._cparams.get('lftlabel', None),
            'rgt': self._cparams.get('rgtlabel', None),
            'center': self._cparams.get('clabel', None)
            }
        if 'label' in self._cparams:
            kwlabels[lblloc] = self._cparams.get('label')

        # Add labels defined in **kwargs to the _userlabels list
        for loc, label in kwlabels.items():
            if label is not None:
                rotate = (theta if lblrotate else 0)
                self.label(label, loc, fontsize=lblsize, rotate=rotate, color=lblcolor)

        for label in self._userlabels:
            if not label.rotate:
                rotate = 0
            elif label.rotate is True:
                rotate = theta
            else:
                rotate = label.rotate
            self._place_label(label.label, loc=label.loc, ofst=label.ofst,
                              align=label.align, rotation=rotate,
                              font=label.font, fontsize=label.fontsize,
                              color=label.color)

        # Add element-specific anchors
        for name, pos in self.anchors.items():
            self.absanchors[name] = self.transform.transform(pos)
        self.absanchors['xy'] = self.transform.transform((0, 0))

        drop = self._cparams.get('drop', None)
        if drop is None or not self._cparams.get('move_cur', True):
            self.absdrop = Point(dwgxy), dwgtheta
        elif self.params.get('droptheta', None):
            self.absdrop = self.transform.transform(drop), self.params.get('droptheta')
        elif self.params.get('theta', None) == 0:
            # Element def specified theta = 0, don't change
            self.absdrop = self.transform.transform(drop), dwgtheta
        else:
            self.absdrop = self.transform.transform(drop), theta
        return self.absdrop

    def get_bbox(self, transform=False, includetext=True):
        ''' Get element bounding box

            Args:
                transform: Apply the element transform to the bbox
                    to get bounds in Drawing coordinates
                includetext: Consider text when calculating bounding
                    box. Text width and height can vary by font,
                    so this produces an estimate of bounds.

            Returns:
                Corners of the bounding box, (xmin, ymin, xmax, ymax)
        '''
        xmin = ymin = math.inf
        xmax = ymax = -math.inf
        for segment in self.segments:
            if not includetext and isinstance(segment, SegmentText): continue
            if transform:
                segment = segment.xform(self.transform)
            segxmin, segymin, segxmax, segymax = segment.get_bbox()
            xmin = min(xmin, segxmin)
            xmax = max(xmax, segxmax)
            ymin = min(ymin, segymin)
            ymax = max(ymax, segymax)

        return BBox(xmin, ymin, xmax, ymax)

    def add_label(self, label, loc='top', ofst=None, align=None,
                  rotation=0, fontsize=None, size=None, font=None, color=None):
        ''' Add a label to the element, after element placement

            Args:
                label: Text to add. If list, list items will be evenly spaced
                    along the element.
                loc: Location for text relative to element, either
                    ['top', 'bot', 'lft', 'rgt'] or name of an anchor
                ofst: Offset between text and element. Defaults to
                    Element.lblofst. Can be list of [x, y] offets.
                align: Tuple of (horizontal, vertical) alignment where
                    horizontal is ['center', 'left', 'right'] and vertical
                    is ['center', 'top', 'bottom']
                rotation: Rotation angle (degrees)
                fontsize: Font size
                font: Font family
                color: Label text color
         '''
        warnings.warn('`add_label` is deprecated. Use `label` instead.', DeprecationWarning)
        if align is None:
            align = (None, None)
        fontsize = fontsize if fontsize else size
        self._place_label(label, loc, ofst, align=align, rotation=rotation,
                          fontsize=fontsize, font=font, color=color)

    def _place_label(self, label: str, loc: LabelLoc=None,
                     ofst: XY | float | None=None, align: Align=(None, None),
                     rotation: float=0, fontsize: float=None,
                     font: str=None, color: str=None) -> None:
        ''' Adds the label Segment to the element, AFTER element placement

            Args:
                label: Text to add. If list, list items will be evenly spaced
                    along the element.
                loc: Location for text relative to element, either
                    ['top', 'bot', 'lft', 'rgt'] or name of an anchor
                ofst: Offset between text and element. Defaults to Element.lblofst.
                    Can be list of [x, y] offets.
                align: Tuple of (horizontal, vertical) alignment where horizontal
                    is ['center', 'left', 'right'] and vertical is ['center',
                    'top', 'bottom']
                rotation: Rotation angle (degrees)
                fontsize: Font size
                font: Font family
                color: Label text color
        '''
        rotation = (rotation + 360) % 360
        if rotation > 90 and rotation < 270:
            rotation -= 180  # Keep the label from going upside down

        if loc is None:
            loc = self._cparams.get('lblloc', 'top')
        loc = {'bot': 'bottom',
               'B': 'bottom',
               'lft': 'left',
               'L': 'left',
               'rgt': 'right',
               'R': 'right',
               'T': 'top'}.get(loc, loc)  # type: ignore

        # This ensures a 'top' label is always on top, regardless of rotation
        theta = self.transform.theta
        if (theta % 360) > 90 and (theta % 360) <= 270:
            if loc == 'top':
                loc = 'bottom'
            elif loc == 'bottom':
                loc = 'top'
            elif loc == 'left':
                loc = 'right'
            elif loc == 'right':
                loc = 'left'

        if align is None and 'lblalign' in self._cparams:
            align = self._cparams['lblalign']
        elif align is None and loc == 'center' and isinstance(label, (list, tuple)):
            align = ('center', 'center')
        elif align is None:
            align = (None, None)
        if None in align:   # Determine best alignment for label based on angle
            th = theta - rotation
            # Below alignment divisions work for label on top. Rotate angle for other sides.
            if loc == 'left':
                th = th + 90
            elif loc == 'bottom':
                th = th + 180
            elif loc == 'right':
                th = th + 270
            th = (th+360) % 360  # Normalize angle so it's positive, clockwise

            rotalign: list[Align] = [('center', 'bottom'),  # label on top
                                     ('right', 'bottom'),
                                     ('right', 'center'),   # label on right
                                     ('right', 'top'),
                                     ('center', 'top'),     # label on bottom
                                     ('left', 'top'),
                                     ('left', 'center'),    # label on left
                                     ('left', 'bottom')]

            # Index into rotalign for a "top" label that's been rotated
            rotalignidx = int(round((th/360)*8) % 8)

            if loc and loc in self.anchors:
                x1, y1, x2, y2 = self.get_bbox(includetext=False)
                if (math.isclose(self.anchors[loc][0], x1, abs_tol=.3) or
                   math.isclose(self.anchors[loc][0], x2, abs_tol=.3) or
                   math.isclose(self.anchors[loc][1], y1, abs_tol=.3) or
                   math.isclose(self.anchors[loc][1], y2, abs_tol=.3)):
                    # Anchor is on an edge
                    dofst = self._cparams.get('lblofst', .1)

                    alignH: Halign
                    alignV: Valign
                    if math.isclose(self.anchors[loc][0], x1, abs_tol=.3):
                        alignH = 'right'
                        ofstx = -dofst
                    elif math.isclose(self.anchors[loc][0], x2, abs_tol=.3):
                        alignH = 'left'
                        ofstx = dofst
                    else:
                        alignH = 'center'
                        ofstx = 0
                    if math.isclose(self.anchors[loc][1], y1, abs_tol=.3):
                        alignV = 'top'
                        ofsty = -dofst
                    elif math.isclose(self.anchors[loc][1], y2, abs_tol=.3):
                        alignV = 'bottom'
                        ofsty = dofst
                    else:
                        alignV = 'center'
                        ofsty = 0

                    align = (align[0] or alignH, align[1] or alignV)
                    rotalignidx = (rotalign.index(align) + round((th/360)*8)) % 8
                    if ofst is None and not isinstance(label, (tuple, list)):
                        ofst = [ofstx, ofsty]
                        
            if loc == 'center':
                align = (align[0] or 'center', align[1] or 'center')
            else:
                ralign = rotalign[rotalignidx]
                align = (align[0] or ralign[0], align[1] or ralign[1])

        xmax = self.bbox.xmax
        xmin = self.bbox.xmin
        ymax = self.bbox.ymax
        ymin = self.bbox.ymin
        if not math.isfinite(xmax+xmin+ymax+ymin):
            xmax = xmin = ymax = ymin = .1

        args: MutableMapping[str, Any] = {}
        if fontsize is not None:
            args['fontsize'] = fontsize
        if font is not None:
            args['font'] = font
        if color is not None:
            args['color'] = color

        lblparams = dict(ChainMap(args, self._cparams))
        lblparams = {'color': lblparams.get('color'),
                     'font': lblparams.get('font'),
                     'fontsize': lblparams.get('fontsize', 14),
                     'align': align,
                     'rotation': rotation}
        if ofst is None:
            ofst = self._cparams.get('lblofst', .1)

        if isinstance(label, (list, tuple)):
            # Divide list along length
            if loc == 'top':
                xdiv = (xmax-xmin)/(len(label)+1)
                ofst = Point((0, ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                for i, lbltxt in enumerate(label):
                    xy = Point((xmin+xdiv*(i+1), ymax))
                    self.segments.append(SegmentText(xy+ofst, lbltxt, **lblparams))
            elif loc == 'bottom':
                xdiv = (xmax-xmin)/(len(label)+1)
                ofst = Point((0, -ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                for i, lbltxt in enumerate(label):
                    xy = Point((xmin+xdiv*(i+1), ymin))
                    self.segments.append(SegmentText(xy+ofst, lbltxt, **lblparams))
            elif loc == 'left':
                ydiv = (ymax-ymin)/(len(label)+1)
                ofst = Point((-ofst, 0)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                for i, lbltxt in enumerate(label):
                    xy = Point((xmin, ymin+ydiv*(i+1)))
                    self.segments.append(SegmentText(xy+ofst, lbltxt, **lblparams))
            elif loc == 'right':
                ydiv = (ymax-ymin)/(len(label)+1)
                ofst = Point((ofst, 0)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                for i, lbltxt in enumerate(label):
                    xy = Point((xmax, ymin+ydiv*(i+1)))
                    self.segments.append(SegmentText(xy+ofst, lbltxt, **lblparams))
            elif loc == 'center':
                xdiv = (xmax-xmin)/(len(label)+1)
                ofst = Point((0, ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                for i, lbltxt in enumerate(label):
                    xy = Point((xmin+xdiv*(i+1), 0))
                    self.segments.append(SegmentText(xy+ofst, lbltxt, **lblparams))

        elif isinstance(label, str):
            # Place in center
            if loc in self.anchors:
                xy = Point(self.anchors[loc])  # type: ignore
                ofst = Point((0, ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                xy = Point(xy)
            elif loc == 'top':
                ofst = Point((0, ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                xy = Point(((xmax+xmin)/2, ymax))
            elif loc == 'bottom':
                ofst = Point((0, -ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)  # type: ignore
                xy = Point(((xmax+xmin)/2, ymin))
            elif loc == 'left':
                ofst = Point((-ofst, 0)) if not isinstance(ofst, (list, tuple)) else Point(ofst)  # type: ignore
                xy = Point((xmin, (ymax+ymin)/2))
            elif loc == 'right':
                ofst = Point((ofst, 0)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                xy = Point((xmax, (ymax+ymin)/2))
            elif loc == 'center':
                ofst = Point((0, ofst)) if not isinstance(ofst, (list, tuple)) else Point(ofst)
                xy = Point(((xmax+xmin)/2, (ymax+ymin)/2))
            else:
                raise ValueError('Undefined location {}'.format(loc))
            xy = xy + ofst
            self.segments.append(SegmentText(xy, label, **lblparams))

    def _draw_on_figure(self):
        ''' Draw the element on a new figure. Useful for _repr_ functions. '''
        fig = Figure(bbox=self.get_bbox(transform=True))
        if not self._cparams:
            self._place((0, 0), 0)
        fig.set_bbox(self.get_bbox(transform=True))
        self._draw(fig)
        return fig

    def _repr_svg_(self):
        ''' SVG representation for Jupyter '''
        fig = self._draw_on_figure()
        return fig.getimage(ext='svg').decode()

    def _repr_png_(self):
        ''' PNG representation for Jupyter '''
        fig = self._draw_on_figure()
        return fig.getimage(ext='png')

    def _draw(self, fig) -> None:
        ''' Draw the element on a Figure '''
        if len(self.segments) == 0:
            self._place((0, 0), 0)
        for segment in self.segments:
            segment.draw(fig, self.transform, **self._cparams)


class ElementDrawing(Element):
    ''' Create an element from a Drawing

        Args:
            drawing: The Drawing instance to convert to an element
    '''
    def __init__(self, drawing, **kwargs):
        super().__init__(**kwargs)
        self.drawing = drawing
        self.segments = self.drawing.get_segments()
        self.params['drop'] = self.drawing.here


class Element2Term(Element):
    ''' Two terminal element. The element leads can be automatically
        extended to the start and ending positions.

        Anchors:
            * start
            * center
            * end
    '''
    def to(self, xy: XY) -> 'Element2Term':
        ''' Sets ending position of element '''
        self._userparams['to'] = xy
        return self

    def tox(self, x: float | XY | Element) -> 'Element2Term':
        ''' Sets ending x-position of element (for horizontal elements) '''
        self._userparams['tox'] = x
        return self

    def toy(self, y: float | XY | Element) -> 'Element2Term':
        ''' Sets ending y-position of element (for vertical elements) '''
        self._userparams['toy'] = y
        return self

    def length(self, length: float) -> 'Element2Term':
        ''' Sets total length of element '''
        self._userparams['l'] = length
        return self

    def endpoints(self, start: XY, end: XY) -> 'Element2Term':
        ''' Sets absolute endpoints of element '''
        assert start is not None
        assert end is not None
        self._userparams['endpts'] = (start, end)
        return self

    def _place(self, dwgxy: XY, dwgtheta: float, **dwgparams) -> tuple[Point, float]:
        ''' Calculate element placement, adding lead extensions '''
        self._dwgparams = dwgparams
        if not self._cparams:
            self._buildparams()

        totlen = self._cparams.get('l', self._cparams.get('unit', 3))
        endpts = self._cparams.get('endpts', None)
        to = self._cparams.get('to', None)
        tox = self._cparams.get('tox', None)
        toy = self._cparams.get('toy', None)
        anchor = self._cparams.get('anchor', None)
        zoom = self._cparams.get('zoom', 1)
        xy = self._cparams.get('at', dwgxy)

        # set up transformation
        theta = self._cparams.get('theta', dwgtheta)
        if endpts is not None:
            theta = util.angle(endpts[0], endpts[1])
        elif self._cparams.get('d') is not None:
            d = self._cparams.get('d')
            if str(d).lstrip('-').isnumeric():
                theta = d
            else:
                theta = {'u': 90, 'r': 0, 'l': 180, 'd': 270}[d[0].lower()]  # type: ignore
        elif to is not None:
            theta = util.angle(xy, to)

        # Get offset to element position within drawing (global shift)
        if endpts is not None:
            xy = Point(endpts[0])

        if endpts is not None:
            totlen = util.dist(endpts[0], endpts[1])
        elif to is not None:
            # Move until X or Y position is 'end'. Depends on direction
            totlen = util.dist(xy, to)
        elif tox is not None:
            # Allow either full coordinate (only keeping x), or just an x value
            if isinstance(tox, (int, float)):
                x = float(tox)
            else:
                x = tox[0]
            endpt = [x, xy[1]]
            totlen = util.dist(xy, endpt)
        elif toy is not None:
            # Allow either full coordinate (only keeping y), or just a y value
            if isinstance(toy, (int, float)):
                y = toy
            else:
                y = toy[1]
            endpt = [xy[0], y]
            totlen = util.dist(xy, endpt)

        if self._cparams.get('extend', True):
            in_path = self.segments[0].path  # type: ignore
            dz = util.delta(in_path[-1], in_path[0])   # Defined delta of path
            in_len = math.hypot(*dz)    # Defined length of path
            lead_len = (totlen - in_len)/2

            if lead_len > 0:  # Don't make element shorter
                start = Point(in_path[0]) - Point((lead_len, 0))
                end = Point(in_path[-1]) + Point((lead_len, 0))
                self._localshift = -start
                self.segments[0].path = [start] + self.segments[0].path + [end]  # type: ignore

            else:
                start = Point(in_path[0])
                end = Point(in_path[-1])
                self._localshift = Point((0, 0))

            # Adjust position of endpoints (arrowheads, dots, etc.)
            for i in range(len(self.segments)):
                if getattr(self.segments[i], 'endref', None) == 'end':
                    xform = Transform(0, end)
                    self.segments[i] = self.segments[i].xform(xform)
                elif getattr(self.segments[i], 'endref', None) == 'start':
                    xform = Transform(0, start)
                    self.segments[i] = self.segments[i].xform(xform)

        self.anchors['start'] = Point(start)
        self.anchors['end'] = Point(end)
        self.anchors['center'] = (start+end)/2

        if anchor is not None:
            self._localshift = self._localshift-Point(self.anchors[anchor])
        transform = Transform(theta, xy, self._localshift, zoom=zoom)

        self.absanchors = {}
        if len(self.segments) == 0:
            self.absanchors['start'] = transform.transform((0, 0))
            self.absanchors['end'] = transform.transform((0, 0))
            self.absanchors['center'] = transform.transform((0, 0))
        else:
            self.absanchors['start'] = transform.transform(start)
            self.absanchors['end'] = transform.transform(end)
            self.absanchors['center'] = transform.transform((start+end)/2)

        self.params['drop'] = end
        return super()._place(xy, theta, **dwgparams)
