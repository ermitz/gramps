#
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2007-2009  Brian G. Matherly
# Copyright (C) 2008       Raphael Ackermann
#               2002-2003  Donald A. Peterson
#               2003       Alex Roitman
#               2009       Benny Malengier
#               2010       Peter Landgren
# Copyright (C) 2011       Adam Stein <adam@csh.rit.edu>
#               2011-2012  Harald Rosemann
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""LaTeX document generator"""

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from bisect import bisect
import re
import os
import logging




#----------------------------------------------------------------------- -
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.plug.docgen import (BaseDoc, 
                                    PAPER_PORTRAIT, FONT_SANS_SERIF)
from gramps.gen.plug.docbackend import DocBackend
from gramps.gen.const import DOCGEN_OPTIONS
from gramps.gen.plug.report import DocOptions
from gramps.gen.plug.menu import BooleanOption
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

_LOG = logging.getLogger(".latexbasedoc")

_CLICKABLE = '\\url{\\1}'


#------------------------------------------------------------------------
#
# LaTeX Article Template
#
#------------------------------------------------------------------------

_LATEX_TEMPLATE = '''%
%
\\usepackage[T1]{fontenc}%
%
% We use latin1 encoding at a minimum by default.
% Gramps uses unicode UTF-8 encoding for its
% international support. LaTeX can deal gracefully
% with unicode encoding by using the ucs style invoked
% when utf8 is specified as an option to the inputenc
% package. This package is included by default in some
% installations, but not in others, so we do not make it
% the default.  Uncomment the first line if you wish to use it
% (If you do not have ucs.sty, you may obtain it from
%  http://www.tug.org/tex-archive/macros/latex/contrib/supported/unicode/)
%
%\\usepackage[latin1]{inputenc}%
\\usepackage[latin1,utf8]{inputenc}%
\\usepackage{graphicx}% Extended graphics support
\\usepackage{longtable}% For multi-page tables
\\usepackage{calc}% For some calculations
\\usepackage{ifthen}% For table width calculations
\\usepackage{ragged2e}% For left aligning with hyphenation
\\usepackage{wrapfig}% wrap pictures in text
\\usepackage{hyperref}% for internal and external links
\\usepackage{xcolor}% to colorize links
\\hypersetup{
    colorlinks,
    linkcolor={red!50!black},
    citecolor={blue!50!black},
    urlcolor={blue!80!black}
}%
\\IfFileExists{libertine.sty}{
    \\usepackage{libertine}
}{}%
\\usepackage[all]{genealogytree}% used by TreeDoc interface
\\usepackage{color}% used by TreeDoc interface
% Depending on your LaTeX installation, the margins may be too
% narrow.  This can be corrected by uncommenting the following
% two lines and adjusting the width appropriately. The example
% removes 0.5in from each margin. (Adds 1 inch to the text)
%\\addtolength{\\oddsidemargin}{-0.5in}%
%\\addtolength{\\textwidth}{1.0in}%
%
% Vertical spacing between paragraphs:
% take one of three possibilities or modify to your taste:
%\\setlength{\\parskip}{1.0ex plus0.2ex minus0.2ex}%
\\setlength{\\parskip}{1.5ex plus0.3ex minus0.3ex}%
%\\setlength{\\parskip}{2.0ex plus0.4ex minus0.4ex}%
%
% Vertical spacing between lines:
% take one of three possibilities or modify to your taste:
\\renewcommand{\\baselinestretch}{1.0}%
%\\renewcommand{\\baselinestretch}{1.1}%
%\\renewcommand{\\baselinestretch}{1.2}%
%
% Indentation; substitute for '1cm' of gramps, 2.5em is right for 12pt
% take one of three possibilities or modify to your taste:
\\newlength{\\grbaseindent}%
%\\setlength{\\grbaseindent}{3.0em}%
\\setlength{\\grbaseindent}{2.5em}%
%\\setlength{\\grbaseindent}{2.0em}%
%
%
% -------------------------------------------------------------
% New lengths, counters and commands for calculations in tables
% -------------------------------------------------------------
%
\\newlength{\\grtabwidth}%
\\newlength{\\grtabprepos}%
\\newlength{\\grreqwidth}%
\\newlength{\\grtempwd}%
\\newlength{\\grmaxwidth}%
\\newlength{\\grprorated}%
\\newlength{\\grxwd}%
\\newlength{\\grwidthused}%
\\newlength{\\grreduce}%
\\newlength{\\grcurcolend}%
\\newlength{\\grspanwidth}%
\\newlength{\\grleadlabelwidth}%
\\newlength{\\grminpgindent}%
\\newlength{\\grlistbacksp}%
\\newlength{\\grpictsize}%
\\newlength{\\grmaxpictsize}%
\\newlength{\\grtextsize}%
\\newlength{\\grmaxtextsize}%
\\newcounter{grtofixcnt}%
\\newcounter{grxwdcolcnt}%
%
%
\\newcommand{\\grinitlength}[2]{%
  \\ifthenelse{\\isundefined{#1}}%
    {\\newlength{#1}}{}%
  \\setlength{#1}{#2}%
}%
%
\\newcommand{\\grinittab}[2]{%    #1: tabwidth, #2 = 1.0/anz-cols
  \\setlength{\\grtabwidth}{#1}%
  \\setlength{\\grprorated}{#2\\grtabwidth}%
  \\setlength{\\grwidthused}{0em}%
  \\setlength{\\grreqwidth}{0em}%
  \\setlength{\\grmaxwidth }{0em}%
  \\setlength{\\grxwd}{0em}%
  \\setlength{\\grtempwd}{0em}%
  \\setlength{\\grpictsize}{0em}%
  \\setlength{\\grmaxpictsize}{0em}%
  \\setlength{\\grtextsize}{0em}%
  \\setlength{\\grmaxtextsize}{0em}%
  \\setlength{\\grcurcolend}{0em}%
  \\setcounter{grxwdcolcnt}{0}%
  \\setcounter{grtofixcnt}{0}%  number of wide cols%
  \\grinitlength{\\grcolbega}{0em}% beg of first col
}%
%
\\newcommand{\\grmaxvaltofirst}[2]{%
  \\ifthenelse{\\lengthtest{#1 < #2}}%
    {\\setlength{#1}{#2}}{}%
}%
%
\\newcommand{\\grsetreqfull}{%
  \\grmaxvaltofirst{\\grmaxpictsize}{\\grpictsize}%
  \\grmaxvaltofirst{\\grmaxtextsize}{\\grtextsize}%
}%
%
\\newcommand{\\grsetreqpart}[1]{%
  \\addtolength{\\grtextsize}{#1 - \\grcurcolend}%
  \\addtolength{\\grpictsize}{#1 - \\grcurcolend}%
  \\grsetreqfull%
}%
%
\\newcommand{\\grdividelength}{%
 \\setlength{\\grtempwd}{\\grtabwidth - \\grwidthused}%
%    rough division of lengths:
%    if 0 < #1 <= 10: \\grxwd = ~\\grtempwd / grtofixcnt
%    otherwise: \\grxwd =  \\grprorated
 \\ifthenelse{\\value{grtofixcnt} > 0}%
  {\\ifthenelse{\\value{grtofixcnt}=1}%
                    {\\setlength{\\grxwd}{\\grtempwd}}{%
    \\ifthenelse{\\value{grtofixcnt}=2}
                    {\\setlength{\\grxwd}{0.5\\grtempwd}}{%
     \\ifthenelse{\\value{grtofixcnt}=3}
                    {\\setlength{\\grxwd}{0.333\\grtempwd}}{%
      \\ifthenelse{\\value{grtofixcnt}=4}
                    {\\setlength{\\grxwd}{0.25\\grtempwd}}{%
       \\ifthenelse{\\value{grtofixcnt}=5}
                    {\\setlength{\\grxwd}{0.2\\grtempwd}}{%
        \\ifthenelse{\\value{grtofixcnt}=6}
                    {\\setlength{\\grxwd}{0.166\\grtempwd}}{%
         \\ifthenelse{\\value{grtofixcnt}=7}
                    {\\setlength{\\grxwd}{0.143\\grtempwd}}{%
          \\ifthenelse{\\value{grtofixcnt}=8}
                    {\\setlength{\\grxwd}{0.125\\grtempwd}}{%
           \\ifthenelse{\\value{grtofixcnt}=9}
                    {\\setlength{\\grxwd}{0.111\\grtempwd}}{%
            \\ifthenelse{\\value{grtofixcnt}=10}
                    {\\setlength{\\grxwd}{0.1\\grtempwd}}{%
             \\setlength{\\grxwd}{\\grprorated}% give up, take \\grprorated%
    }}}}}}}}}}%
  \\setlength{\\grreduce}{0em}%
  }{\\setlength{\\grxwd}{0em}}%
}%
%
\\newcommand{\\grtextneedwidth}[1]{%
  \\settowidth{\\grtempwd}{#1}%
  \\grmaxvaltofirst{\\grtextsize}{\\grtempwd}%
}%
%
\\newcommand{\\grcolsfirstfix}[5]{%
  \\grinitlength{#1}{\\grcurcolend}%
  \\grinitlength{#3}{0em}%
  \\grinitlength{#4}{\\grmaxpictsize}%
  \\grinitlength{#5}{\\grmaxtextsize}%
  \\grinitlength{#2}{#5}%
  \\grmaxvaltofirst{#2}{#4}%
  \\addtolength{#2}{2\\tabcolsep}%
  \\grmaxvaltofirst{\\grmaxwidth}{#2}%
  \\ifthenelse{\\lengthtest{#2 < #4} \\or \\lengthtest{#2 < \\grprorated}}%
    { \\setlength{#3}{#2}%
      \\addtolength{\\grwidthused}{#2} }%
    { \\stepcounter{grtofixcnt} }%
  \\addtolength{\\grcurcolend}{#2}%
}%
%
\\newcommand{\\grcolssecondfix}[4]{%
  \\ifthenelse{\\lengthtest{\\grcurcolend < \\grtabwidth}}%
    { \\setlength{#3}{#2} }%
    { \\addtolength{#1}{-\\grreduce}%
      \\ifthenelse{\\lengthtest{#2 = \\grmaxwidth}}%
        { \\stepcounter{grxwdcolcnt}}%
        { \\ifthenelse{\\lengthtest{#3 = 0em} \\and %
                       \\lengthtest{#4 > 0em}}%
            { \\setlength{\\grtempwd}{#4}%
              \\grmaxvaltofirst{\\grtempwd}{\\grxwd}%
              \\addtolength{\\grreduce}{#2 - \\grtempwd}%
              \\setlength{#2}{\\grtempwd}%
              \\addtolength{\\grwidthused}{#2}%
              \\addtocounter{grtofixcnt}{-1}%
              \\setlength{#3}{#2}%
            }{}%
        }%
    }%
}%
%
\\newcommand{\\grcolsthirdfix}[3]{%
  \\ifthenelse{\\lengthtest{\\grcurcolend < \\grtabwidth}}%
    {}{ \\addtolength{#1}{-\\grreduce}%
        \\ifthenelse{\\lengthtest{#3 = 0em} \\and %
                     \\lengthtest{#2 < \\grmaxwidth}}%
          { \\ifthenelse{\\lengthtest{#2 < 0.5\\grmaxwidth}}%
              { \\setlength{\\grtempwd}{0.5\\grxwd}%
                \\grmaxvaltofirst{\\grtempwd}{0.7\\grprorated}}%
              { \\setlength{\\grtempwd}{\\grxwd}}%
            \\addtolength{\\grreduce}{#2 - \\grtempwd}%
            \\setlength{#2}{\\grtempwd}%
            \\addtolength{\\grwidthused}{#2}%
            \\addtocounter{grtofixcnt}{-1}%
            \\setlength{#3}{#2}%
          }{}%
      }%
}%
%
\\newcommand{\\grcolsfourthfix}[3]{%
  \\ifthenelse{\\lengthtest{\\grcurcolend < \\grtabwidth}}%
    {}{ \\addtolength{#1}{-\\grreduce}%
        \\ifthenelse{\\lengthtest{#3 = 0em}}%
          { \\addtolength{\\grreduce}{#2 - \\grxwd}%
            \\setlength{#2}{\\grxwd}%
            \\setlength{#3}{#2}%
          }{}%
      }%
}%
%
\\newcommand{\\grgetspanwidth}[4]{%
  \\grinitlength{#1}{#3 - #2 + #4}%
}%
%
\\newcommand{\\tabheadstrutceil}{%
  \\rule[0.0ex]{0.00em}{3.5ex}}%
\\newcommand{\\tabheadstrutfloor}{%
  \\rule[-2.0ex]{0.00em}{2.5ex}}%
\\newcommand{\\tabrowstrutceil}{%
  \\rule[0.0ex]{0.00em}{2.9ex}}%
\\newcommand{\\tabrowstrutfloor}{%
  \\rule[-0.1ex]{0.00em}{2.0ex}}%
%
\\newcommand{\\grempty}[1]{}%
%
\\newcommand{\\graddvdots}[1]{%
  \\hspace*{\\fill}\\hspace*{\\fill}\\raisebox{#1}{\\vdots}%
}%
%
\\newcommand{\\grtabpgbreak}[4]{%
  #1 { \\parbox[t]{ #2 - 2\\tabcolsep}{\\tabheadstrutceil\\hspace*{\\fill}%
  \\raisebox{#4}{\\vdots} #3{#4} \\hspace*{\\fill}\\tabheadstrutfloor}}%
}%
%
\\newcommand{\\grcolpart}[3]{%
  #1 { \\parbox[t]{ #2 - 2\\tabcolsep}%
  {\\tabrowstrutceil #3~\\\\[-1.6ex]\\tabrowstrutfloor}}%
}%
%
\\newcommand{\\grminpghead}[2]{%
  \\setlength{\\grminpgindent}{#1\\grbaseindent-\\grlistbacksp}%
  \\hspace*{\\grminpgindent}%
  \\ifthenelse{\\not \\lengthtest{#2em > 0em}}%
    {\\begin{minipage}[t]{\\textwidth -\\grminpgindent}}%
    {\\begin{minipage}[t]{\\textwidth -\\grminpgindent%
        -#2\\grbaseindent -4\\tabcolsep}}%
}%
%
\\newcommand{\\grminpgtail}{%
  \\end{minipage}\\parindent0em%
}%
%
\\newcommand{\\grlisthead}[1]{%
  \\begin{list}{#1}%
    { \\setlength{\\labelsep}{0.5em}%
      \\setlength{\\labelwidth}{\\grleadlabelwidth}%
      \\setlength{\\leftmargin}{\\grlistbacksp}%
    }\\item%
}%
%
\\newcommand{\\grlisttail}{%
  \\end{list}%
}%
%
\\newcommand{\\grprepleader}[1]{%
  \\settowidth{\\grtempwd}{#1}%
  \\ifthenelse{\\lengthtest{\\grtempwd > \\grleadlabelwidth}}%
    { \\setlength{\\grleadlabelwidth}{\\grtempwd}}{}%
  \\setlength{\\grlistbacksp}{\\grleadlabelwidth + 1.0em}%
}%
%
\\newcommand{\\grprepnoleader}{%
  \\setlength{\\grleadlabelwidth}{0em}%
  \\setlength{\\grlistbacksp}{0em}%
}%
%
\\newcommand{\\grmkpicture}[4]{%
    \\begin{wrapfigure}{r}{#2\\grbaseindent}%
      \\vspace{-6ex}%
      \\begin{center}%
      \\includegraphics[%
        width= #2\\grbaseindent,%
        height= #3\\grbaseindent,%
          keepaspectratio]%
        {#1}\\\\%
      {\\RaggedRight\\footnotesize#4}%
      \\end{center}%
    \\end{wrapfigure}%
    \\settowidth{\\grtempwd}{\\footnotesize#4}%
    \\setlength{\\grxwd}{#2\\grbaseindent}%
    \\ifthenelse{\\lengthtest{\\grtempwd < 0.7\\grxwd}}%
                    {\\setlength{\\grxwd}{1ex}}{%
      \\ifthenelse{\\lengthtest{\\grtempwd < 1.2\\grxwd}}%
                    {\\setlength{\\grxwd}{2ex}}{%
        \\ifthenelse{\\lengthtest{\\grtempwd < 1.8\\grxwd}}%
                    {\\setlength{\\grxwd}{6ex}}{%
          \\ifthenelse{\\lengthtest{\\grtempwd < 2.0\\grxwd}}%
                    {\\setlength{\\grxwd}{10ex}}{%
                     \\setlength{\\grxwd}{12ex}}%
                    }}}%
  \\setlength{\\grtempwd}{#3\\grbaseindent + \\grxwd}%
  \\rule[-\\grtempwd]{0pt}{\\grtempwd}%
  \\setlength{\\grtabprepos}{-\\grtempwd}%
}%
%
%
\\begin{document}%
'''


#------------------------------------------------------------------------
#
# Font size table and function
#
#------------------------------------------------------------------------

# These tables correlate font sizes to LaTeX.  The first table contains
# typical font sizes in points.  The second table contains the standard
# LaTeX font size names. Since we use bisect to map the first table to the
# second, we are guaranteed that any font less than 6 points is 'tiny', fonts
# from 6-7 points are 'script', etc. and fonts greater than or equal to 22
# are considered 'Huge'.  Note that fonts from 12-13 points are not given a
# LaTeX font size name but are considered "normal."

_FONT_SIZES = [6, 8, 10, 12, 14, 16, 18, 20, 22]
_FONT_NAMES = ['tiny', 'scriptsize', 'footnotesize', 'small', '',
               'large', 'Large', 'LARGE', 'huge', 'Huge']

def map_font_size(fontsize):
    """ Map font size in points to LaTeX font size """
    return _FONT_NAMES[bisect(_FONT_SIZES, fontsize)]


#------------------------------------------------------------------------
#
# auxiliaries to facilitate table construction
#
#------------------------------------------------------------------------

# patterns for regular expressions, module re:
TBLFMT_PAT = re.compile(r'({\|?)l(\|?})')

# constants for routing in table construction:
(CELL_BEG, CELL_TEXT, CELL_END, ROW_BEG, ROW_END, TAB_BEG,
 TAB_END) = list(range(7))
FIRST_ROW, SUBSEQ_ROW = list(range(2))


#------------------------------------------------------------------------
#
# Paragraph Handling
#
#------------------------------------------------------------------------

class TexFont:
    def __init__(self, style=None):
        if style:
            self.font_beg = style.font_beg
            self.font_end = style.font_end
            self.left_indent = style.left_indent
            self.first_line_indent = style.first_line_indent
        else:
            self.font_beg = ""
            self.font_end = ""
            self.left_indent = ""
            self.first_line_indent = ""



#------------------------------------------------------------------------
#
# Functions for docbackend
#
#------------------------------------------------------------------------
def latexescape(text):
    """
    Escape the following special characters: & $ % # _ { }
    """
    text = text.replace('&', '\\&')
    text = text.replace('$', '\\$')
    text = text.replace('%', '\\%')
    text = text.replace('#', '\\#')
    text = text.replace('_', '\\_')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    # replace character unknown to LaTeX
    text = text.replace('→', '$\\longrightarrow$')
    return text

ESCAPE_PAT = re.compile('|'.join([re.escape(key) for key in
       {
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '~': '\\~{}',
        '^': '\\^{}',
        '\\': '\\textbackslash{}'
        }.keys()]))

def escape(text):
    lookup = {
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}',
        '~': '\\~{}',
        '^': '\\^{}',
        '\\': '\\textbackslash{}'
        }
    pattern = re.compile('|'.join([re.escape(key) for key in lookup.keys()]))
    return pattern.sub(lambda match: lookup[match.group(0)], text)


def latexescapeverbatim(text):
    """
    Escape special characters and also make sure that LaTeX respects whitespace
    and newlines correctly.
    """
    text = latexescape(text)
    text = text.replace(' ', '\\ ')
    text = text.replace('\n', '~\\newline \n')
    #spaces at begin are normally ignored, make sure they are not.
    #due to above a space at begin is now \newline\n\
    text = text.replace('\\newline\n\\ ',
                        '\\newline\n\\hspace*{0.1\\grbaseindent}\\ ')
    return text

#------------------------------------------------------------------------
#
# Document Backend class for cairo docs
#
#------------------------------------------------------------------------

class LaTeXBackend(DocBackend):
    """
    Implementation of docbackend for latex docs.
    File and File format management for latex docs
    """
    # overwrite base class attributes, they become static var of LaTeXDoc
    SUPPORTED_MARKUP = [
        DocBackend.BOLD,
        DocBackend.ITALIC,
        DocBackend.UNDERLINE,
        DocBackend.FONTSIZE,
        DocBackend.FONTFACE,
        DocBackend.SUPERSCRIPT]

    STYLETAG_MARKUP = {
        DocBackend.BOLD        : ("\\textbf{", "}"),
        DocBackend.ITALIC      : ("\\textit{", "}"),
        DocBackend.UNDERLINE   : ("\\underline{", "}"),
        DocBackend.SUPERSCRIPT : ("\\textsuperscript{", "}"),
    }

    ESCAPE_FUNC = lambda x: latexescape

    def setescape(self, preformatted=False):
        """
        LaTeX needs two different escape functions depending on the type.
        This function allows to switch the escape function
        """
        if not preformatted:
            LaTeXBackend.ESCAPE_FUNC = lambda x: latexescape
        else:
            LaTeXBackend.ESCAPE_FUNC = lambda x: latexescapeverbatim

    def _create_xmltag(self, type, value):
        r"""
        overwrites the method in DocBackend.
        creates the latex tags needed for non bool style types we support:
            FONTSIZE : use different \large denomination based
                                        on size
                                     : very basic, in mono in the font face
                                        then we use {\ttfamily }
        """
        if type not in self.SUPPORTED_MARKUP:
            return None
        elif type == DocBackend.FONTSIZE:
            #translate size in point to something LaTeX can work with
            fontsize = map_font_size(value)
            if fontsize:
                return ("{\\" + fontsize + ' ', "}")
            else:
                return ("", "")

        elif type == DocBackend.FONTFACE:
            if 'MONO' in value.upper():
                return ("{\\ttfamily ", "}")
            elif 'ROMAN' in value.upper():
                return ("{\\rmfamily ", "}")
        return None

    def _checkfilename(self):
        """
        Check to make sure filename satisfies the standards for this filetype
        """
        if not self._filename.endswith(".tex"):
            self._filename = self._filename + ".tex"


#------------------------------------------------------------------
#
# LaTeXDoc
#
#------------------------------------------------------------------

class LaTeXBaseDoc(BaseDoc):
    """LaTeX document interface class. Derived from BaseDoc"""

#   ---------------------------------------------------------------
#   some additional variables
#   ---------------------------------------------------------------
    in_table = False
    in_multrow_cell = False #   for tab-strukt: cols of rows
    pict = ''
    pict_in_table = False
    pict_width = 0
    pict_height = 0
    textmem = []
    in_title = True


    def __init__(self, styles, paper_style, options=None, uistate=None):
        BaseDoc.__init__(self, styles, paper_style, options, uistate)

        if options:
           get_option = options.menu.get_option_by_name
           option = get_option('tex_gen_preamble')
           if option:
              self.with_preamble = option.get_value()
           else:
              self.with_preamble = True



#   ---------------------------------------------------------------
#   begin of table special treatment
#   ---------------------------------------------------------------
    def emit(self, text, level=0):
        """
        Hand over all text but tables to self._backend.write(), (line 1-2).
        In case of tables pass to specal treatment below.
        """
        if level:
            text = '  '*level + text
        self._backend.write(text)


        # BaseDoc interface
    def open(self, filename):
        """Opens the specified file, making sure that it has the
        extension of .tex"""
        self._backend = LaTeXBackend(filename)
        self._backend.open()

        # Font size control seems to be limited. For now, ignore
        # any style constraints, and use 12pt as the default

        fontsize = "12pt"

        paper_size = self.paper.get_size()
        name = paper_size.get_name().lower()
        if name == 'custom size':
            width = str(paper_size.get_width())
            height = str(paper_size.get_height())
            paper = 'papersize={%scm,%scm}' % (width, height)
        elif name in ('a', 'b', 'c', 'd', 'e'):
            paper = 'ansi' + name + 'paper'
        else:
            paper = name + 'paper'
 
        if self.paper.get_orientation() == PAPER_PORTRAIT:
            orientation = 'portrait'
        else:
            orientation = 'landscape'

        lmargin = self.paper.get_left_margin()
        rmargin = self.paper.get_right_margin()
        tmargin = self.paper.get_top_margin()
        bmargin = self.paper.get_bottom_margin()
        if lmargin == rmargin == tmargin == bmargin:
            margin = 'margin=%scm'% lmargin
        else:
            if lmargin == rmargin:
                margin = 'hmargin=%scm' % lmargin
            else:
                margin = 'hmargin={%scm,%scm}' % (lmargin, rmargin)
            if tmargin == bmargin:
                margin += ',vmargin=%scm' % tmargin
            else:
                margin += ',vmargin={%scm,%scm}' % (tmargin, bmargin)


        # Use the article template, T1 font encodings, and specify
        # that we should use Latin1 and unicode character encodings.
        if self.with_preamble:
            self.emit('\\documentclass[%s,%s,%s]{article}\n' % (fontsize,paper,orientation))
            self.emit('\\usepackage[%s,%s]{geometry}\n' % (paper, margin))
            self.emit(_LATEX_TEMPLATE)

        self.in_list = False
        self.in_table = False
        self.head_line = False

        #Establish some local styles for the report
        self.latexstyle = {}
        self.latex_font = {}

        style_sheet = self.get_style_sheet()
        for style_name in style_sheet.get_paragraph_style_names():
            style = style_sheet.get_paragraph_style(style_name)
            font = style.get_font()
            size = font.get_size()

            self.latex_font[style_name] = TexFont()
            thisstyle = self.latex_font[style_name]

            thisstyle.font_beg = ""
            thisstyle.font_end = ""
            # Is there special alignment?  (default is left)
            align = style.get_alignment_text()
            if  align == "center":
                thisstyle.font_beg += "{\\centering"
                thisstyle.font_end = ''.join(("\n\n}", thisstyle.font_end))
            elif align == "right":
                thisstyle.font_beg += "\\hfill"

            # Establish font face and shape
            if font.get_type_face() == FONT_SANS_SERIF:
                thisstyle.font_beg += "\\sffamily"
                thisstyle.font_end = "\\rmfamily" + thisstyle.font_end
            if font.get_bold():
                thisstyle.font_beg += "\\bfseries"
                thisstyle.font_end = "\\mdseries" + thisstyle.font_end
            if font.get_italic() or font.get_underline():
                thisstyle.font_beg += "\\itshape"
                thisstyle.font_end = "\\upshape" + thisstyle.font_end

            # Now determine font size
            fontsize = map_font_size(size)
            if fontsize:
                thisstyle.font_beg += "\\" + fontsize
                thisstyle.font_end += "\\normalsize"

            thisstyle.font_beg += " "
            thisstyle.font_end += " "

            left = style.get_left_margin()
            first = style.get_first_indent() + left
            thisstyle.left_indent = left
            thisstyle.first_line_indent = first
            self.latexstyle[style_name] = thisstyle

        # BaseDoc interface
    def close(self):
        """Clean up and close the document"""
        if self.in_list:
            self.emit('\\end{list}\n')
        if self.with_preamble:
            self.emit('\\end{document}\n')
        self._backend.close()



class LaTeXBaseDocOptions(DocOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name='zorg'):
        DocOptions.__init__(self, name)

    def add_menu_options(self, menu):
        """
        Add options to the document menu for the docgen.
        """

        category_name = DOCGEN_OPTIONS

        gen_preamble  = BooleanOption(_('Generate LaTeX preamble') , True)
        gen_preamble.set_help(_('Generate preamble. Unselect if you want to '
                                'include your tex file in a global book file'))

        menu.add_option(category_name, 'tex_gen_preamble', gen_preamble)
