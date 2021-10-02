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

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False




#----------------------------------------------------------------------- -
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.lib import EventType, Date
from gramps.gen.plug.docgen import (TextDoc, URL_PATTERN)
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.plugins.docgen.latexbasedoc import LaTeXBaseDoc, LaTeXBaseDocOptions
from gramps.plugins.docgen.latexbasedoc import latexescape, latexescapeverbatim
_ = glocale.translation.gettext

_LOG = logging.getLogger(".latexdoc")

_CLICKABLE = '\\url{\\1}'

#------------------------------------------------------------------------
#
# Special settings for LaTeX output
#
#------------------------------------------------------------------------
#   For an interim mark e.g. for an intended linebreak I use a special pattern.
#   It shouldn't interfere with normal text. In LaTeX character '&' is used
#   for column separation in tables and may occur there in series. The pattern
#   is used here before column separation is set. On the other hand incoming
#   text can't show this pattern for it would have been replaced by '\&\&'.
#   So the choosen pattern will do the job without confusion:

SEPARATION_PAT = '&&'



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


def get_charform(col_num):
    """
    Transfer column number to column charakter,
    limited to letters within a-z;
    26, there is no need for more.
    early test of column count in start_table()
    """
    if col_num > ord('z') - ord('a'):
        raise ValueError(''.join((
            '\n number of table columns is ', repr(col_num),
            '\n                     should be <= ', repr(ord('z') - ord('a')))))
    return chr(ord('a') + col_num)

def get_numform(col_char):
    return ord(col_char) - ord('a')


#------------------------------------------
#   row_alph_counter = str_incr(MULTCOL_COUNT_BASE)
#
#   'aaa' is sufficient for up to 17576 multicolumns in each table;
#   do you need more?
#   uncomment one of the two lines
MULTCOL_COUNT_BASE = 'aaa'
# MULTCOL_COUNT_BASE = 'aaaa'
#------------------------------------------

def str_incr(str_counter):
    """ for counting table rows """
    lili = list(str_counter)
    while 1:
        yield ''.join(lili)
        if ''.join(lili) == len(lili)*'z':
            raise ValueError(''.join((
                '\n can\'t increment string ', ''.join(lili),
                ' of length ', str(len(lili)))))
        for i in range(len(lili)-1, -1, -1):
            if lili[i] < 'z':
                lili[i] = chr(ord(lili[i])+1)
                break
            else:
                lili[i] = 'a'

#------------------------------------------------------------------------
#
# Structure of Table-Memory
#
#------------------------------------------------------------------------

class TabCell:
    def __init__(self, colchar, span, head, content):
        self.colchar = colchar
        self.span = span
        self.head = head
        self.content = content
class TabRow:
    def __init__(self):
        self.cells = []
        self.tail = ''
        self.addit = '' # for: \\hline, \\cline{}
class TabMem:
    def __init__(self, head):
        self.head = head
        self.tail = ''
        self.rows = []




#------------------------------------------------------------------
#
# LaTeXDoc
#
#------------------------------------------------------------------

class LaTeXDoc(LaTeXBaseDoc, TextDoc):
    """LaTeX document interface class. Derived from LaTeXBaseDoc"""

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
        LaTeXBaseDoc.__init__(self, styles, paper_style, options, uistate)




#   ---------------------------------------------------------------
#   begin of table special treatment
#   ---------------------------------------------------------------
    def emit(self, text, level=0, tab_state=CELL_TEXT, span=1):
        """
        Hand over all text but tables to self._backend.write(), (line 1-2).
        In case of tables pass to specal treatment below.
        """
        if level:
            text = '  '*level + text
        if not self.in_table: # all stuff but table
            LaTeXBaseDoc.emit(self,text, level)
        else:
            self.handle_table(text, tab_state, span)


    def handle_table(self, text, tab_state, span):
        """
        Collect tables elements in an adequate cell/row/table structure and
        call for LaTeX width calculations and writing out
        """
        if tab_state == CELL_BEG:
            # here text is head
            self.textmem = []
            self.curcol_char = get_charform(self.curcol-1)
            if span > 1: # phantom columns prior to multicolumns
                for col in range(self.curcol - span, self.curcol - 1):
                    col_char = get_charform(col)
                    phantom = TabCell(col_char, 0, '', '')
                    self.tabrow.cells.append(phantom)
            self.tabcell = TabCell(self.curcol_char, span, text, '')
        elif tab_state == CELL_TEXT:
            self.textmem.append(text)
        elif tab_state == CELL_END: # text == ''
            self.tabcell.content = ''.join(self.textmem).strip()

            if self.tabcell.content.find('\\centering') != -1:
                self.tabcell.content = self.tabcell.content.replace(
                    '\\centering', '')
                self.tabcell.head = re.sub(
                    TBLFMT_PAT, '\\1c\\2', self.tabcell.head)
            self.tabrow.cells.append(self.tabcell)
            self.textmem = []
        elif tab_state == ROW_BEG:
            self.tabrow = TabRow()
        elif tab_state == ROW_END:
            self.tabrow.addit = text # text: \\hline, \\cline{}
            self.tabrow.tail = ''.join(self.textmem) # \\\\ row-termination
            if self.in_multrow_cell: #   cols of rows: convert to rows of cols
                self.repack_row()
            else:
                self.tabmem.rows.append(self.tabrow)
        elif tab_state == TAB_BEG: # text: \\begin{longtable}[l]{
            self._backend.write(''.join(('\\grinittab{\\textwidth}{',
                                         repr(1.0/self.numcols), '}%\n')))
            self.tabmem = TabMem(text)
        elif tab_state == TAB_END: # text: \\end{longtable}
            self.tabmem.tail = text

            # table completed, calc widths and write out
            self.calc_latex_widths()
            self.write_table()


    def repack_row(self):
        """
        Transpose contents contained in a row of cols of cells
        to rows of cells with corresponding contents.
        Cols of the mult-row-cell are ended by SEPARATION_PAT
        """
        # if last col empty: delete
        if self.tabrow.cells[-1].content == '':
            del self.tabrow.cells[-1]
            self.numcols -= 1

        # extract cell.contents
        bare_contents = [cell.content.strip(SEPARATION_PAT).replace(
            '\n', '').split(SEPARATION_PAT) for cell in self.tabrow.cells]

        # mk equal length & transpose
        num_new_rows = max([len(mult_row_cont)
                            for mult_row_cont in bare_contents])
        cols_equ_len = []
        for mrc in bare_contents:
            for i in range(num_new_rows - len(mrc)):
                mrc.append('')
            cols_equ_len.append(mrc)
        transp_cont = list(zip(*cols_equ_len))

        # picts? extract
        first_cell, last_cell = (0, self.numcols)
        if self.pict_in_table:
            if transp_cont[0][-1].startswith('\\grmkpicture'):
                self.pict = transp_cont[0][-1]
                last_cell -= 1
                self.numcols -= 1
                self._backend.write(''.join(
                    ('\\addtolength{\\grtabwidth}{-',
                     repr(self.pict_width),
                     '\\grbaseindent -2\\tabcolsep}%\n')))
            self.pict_in_table = False

        # new row-col structure
        for row in range(num_new_rows):
            new_row = TabRow()
            for i in range(first_cell, last_cell):
                new_cell = TabCell(
                    get_charform(i + first_cell),
                    self.tabrow.cells[i].span, self.tabrow.cells[i].head,
                    transp_cont[row][i + first_cell])
                new_row.cells.append(new_cell)
            new_row.tail = self.tabrow.tail
            new_row.addit = ''
            self.tabmem.rows.append(new_row)

        self.tabmem.rows[-1].addit = self.tabrow.addit
        self.in_multrow_cell = False

    def calc_latex_widths(self):
        """
        Control width settings in latex table construction
        Evaluations are set up here and passed to LaTeX
        to calculate required and to fix suitable widths.
        ??? Can all this be done exclusively in TeX? Don't know how.
        """
        tabcol_chars = []
        for col_num in range(self.numcols):
            col_char = get_charform(col_num)
            tabcol_chars.append(col_char)
            for row in self.tabmem.rows:
                cell = row.cells[col_num]
                if cell.span == 0:
                    continue
                if cell.content.startswith('\\grmkpicture'):
                    self._backend.write(
                        ''.join(('\\setlength{\\grpictsize}{',
                                 self.pict_width, '\\grbaseindent}%\n')))
                else:
                    for part in cell.content.split(SEPARATION_PAT):
                        self._backend.write(
                            ''.join(('\\grtextneedwidth{', part, '}%\n')))
                    row.cells[col_num].content = cell.content.replace(
                        SEPARATION_PAT, '~\\newline \n')

                if cell.span == 1:
                    self._backend.write(''.join(('\\grsetreqfull%\n')))
                elif cell.span > 1:
                    self._backend.write(
                        ''.join(('\\grsetreqpart{\\grcolbeg',
                                 get_charform(get_numform(cell.colchar) -
                                              cell.span +1),
                                 '}%\n')))

            self._backend.write(
                ''.join(('\\grcolsfirstfix',
                         ' {\\grcolbeg', col_char, '}{\\grtempwidth', col_char,
                         '}{\\grfinalwidth', col_char, '}{\\grpictreq',
                         col_char, '}{\\grtextreq', col_char, '}%\n')))

        self._backend.write(''.join(('\\grdividelength%\n')))
        for col_char in tabcol_chars:
            self._backend.write(
                ''.join(('\\grcolssecondfix',
                         ' {\\grcolbeg', col_char, '}{\\grtempwidth', col_char,
                         '}{\\grfinalwidth', col_char, '}{\\grpictreq',
                         col_char, '}%\n')))

        self._backend.write(''.join(('\\grdividelength%\n')))
        for col_char in tabcol_chars:
            self._backend.write(
                ''.join(('\\grcolsthirdfix',
                         ' {\\grcolbeg', col_char, '}{\\grtempwidth', col_char,
                         '}{\\grfinalwidth', col_char, '}%\n')))

        self._backend.write(''.join(('\\grdividelength%\n')))
        for col_char in tabcol_chars:
            self._backend.write(
                ''.join(('\\grcolsfourthfix',
                         ' {\\grcolbeg', col_char, '}{\\grtempwidth', col_char,
                         '}{\\grfinalwidth', col_char, '}%\n')))

        self.multcol_alph_counter = str_incr(MULTCOL_COUNT_BASE)
        for row in self.tabmem.rows:
            for cell in row.cells:
                if cell.span > 1:
                    multcol_alph_id = next(self.multcol_alph_counter)
                    self._backend.write(
                        ''.join(('\\grgetspanwidth{',
                                 '\\grspanwidth', multcol_alph_id,
                                 '}{\\grcolbeg', get_charform(
                                     get_numform(cell.colchar)- cell.span + 1),
                                 '}{\\grcolbeg', cell.colchar,
                                 '}{\\grtempwidth', cell.colchar,
                                 '}%\n')))

    def write_table(self):
        # Choosing RaggedRight (with hyphenation) in table and
        # provide manually adjusting of column widths
        self._backend.write(
            ''.join((
                '%\n', self.pict,
                '%\n%\n',
                '%  ==> Comment out one of the two lines ',
                'by a leading "%" (first position)\n',
                '{ \\RaggedRight%      left align with hyphenation in table \n',
                '%{%                no left align in table \n%\n',
                '%  ==>  You may add pos or neg values ',
                'to the following ', repr(self.numcols), ' column widths %\n')))
        for col_num in range(self.numcols):
            self._backend.write(
                ''.join(('\\addtolength{\\grtempwidth',
                         get_charform(col_num), '}{+0.0cm}%\n')))
        self._backend.write('%  === %\n')

        # adjust & open table':
        if self.pict:
            self._backend.write(
                ''.join(('%\n\\vspace{\\grtabprepos}%\n',
                         '\\setlength{\\grtabprepos}{0ex}%\n')))
            self.pict = ''
        self._backend.write(''.join(self.tabmem.head))

        # special treatment at begin of longtable for heading and
        # closing at top and bottom of table
        # and parts of it at pagebreak separating
        self.multcol_alph_counter = str_incr(MULTCOL_COUNT_BASE)
        splitting_row = self.mk_splitting_row(self.tabmem.rows[FIRST_ROW])
        self.multcol_alph_counter = str_incr(MULTCOL_COUNT_BASE)
        complete_row = self.mk_complete_row(self.tabmem.rows[FIRST_ROW])

        self._backend.write(splitting_row)
        self._backend.write('\\endhead%\n')
        self._backend.write(splitting_row.replace('{+2ex}', '{-2ex}'))
        self._backend.write('\\endfoot%\n')
        if self.head_line:
            self._backend.write('\\hline%\n')
            self.head_line = False
        else:
            self._backend.write('%\n')
        self._backend.write(complete_row)
        self._backend.write('\\endfirsthead%\n')
        self._backend.write('\\endlastfoot%\n')

        # hand over subsequent rows
        for row in self.tabmem.rows[SUBSEQ_ROW:]:
            self._backend.write(self.mk_complete_row(row))

        # close table by '\\end{longtable}', end '{\\RaggedRight' or '{' by '}'
        self._backend.write(''.join((''.join(self.tabmem.tail), '}%\n\n')))

    def mk_splitting_row(self, row):
        splitting = []
        add_vdots = '\\grempty'
        for cell in row.cells:
            if cell.span == 0:
                continue
            if (not splitting and
                    get_numform(cell.colchar) == self.numcols - 1):
                add_vdots = '\\graddvdots'
            if cell.span == 1:
                cell_width = ''.join(('\\grtempwidth', cell.colchar))
            else:
                cell_width = ''.join(('\\grspanwidth',
                                      next(self.multcol_alph_counter)))
            splitting.append(
                ''.join(('\\grtabpgbreak{', cell.head, '}{',
                         cell_width, '}{', add_vdots, '}{+2ex}%\n')))
        return ''.join((' & '.join(splitting), '%\n', row.tail))

    def mk_complete_row(self, row):
        complete = []
        for cell in row.cells:
            if cell.span == 0:
                continue
            elif cell.span == 1:
                cell_width = ''.join(('\\grtempwidth', cell.colchar))
            else:
                cell_width = ''.join(('\\grspanwidth',
                                      next(self.multcol_alph_counter)))
            complete.append(
                ''.join(('\\grcolpart{%\n  ', cell.head, '}{%\n', cell_width,
                         '}{%\n  ', cell.content, '%\n}%\n')))
        return ''.join((' & '.join(complete), '%\n', row.tail, row.addit))

#       ---------------------------------------------------------------------
#       end of special table treatment
#       ---------------------------------------------------------------------

        # TextDoc interface
    def page_break(self):
        "Forces a page break, creating a new page"
        self.emit('\\newpage%\n')

    def end_page(self):
        """Issue a new page command"""
        self.emit('\\newpage')

        # TextDoc interface
    def start_paragraph(self, style_name, leader=None):
        """Paragraphs handling - A Gramps paragraph is any
        single body of text from a single word to several sentences.
        We assume a linebreak at the end of each paragraph."""
        style_sheet = self.get_style_sheet()

        style = style_sheet.get_paragraph_style(style_name)
        ltxstyle = self.latexstyle[style_name]
        self.level = style.get_header_level()

        self.fbeg = ltxstyle.font_beg
        self.fend = ltxstyle.font_end

        self.indent = ltxstyle.left_indent
        self.first_line_indent = ltxstyle.first_line_indent
        if self.indent == 0:
            self.indent = self.first_line_indent

        # For additional vertical space beneath title line(s)
        # i.e. when the first centering ended:
        if self.in_title and ltxstyle.font_beg.find('centering') == -1:
            self.in_title = False
            self._backend.write('\\vspace{5ex}%\n')
        if self.in_table:   #   paragraph in table indicates: cols of rows
            self.in_multrow_cell = True
        else:
            if leader:
                self._backend.write(
                    ''.join(('\\grprepleader{', leader, '}%\n')))
            else:
                self._backend.write('\\grprepnoleader%\n')

#           -------------------------------------------------------------------
            #   Gramps presumes 'cm' as units; here '\\grbaseindent' is used
            #   as equivalent, set in '_LATEX_TEMPLATE' above to '3em';
            #   there another value might be choosen.
#           -------------------------------------------------------------------
            if self.indent is not None:
                self._backend.write(
                    ''.join(('\\grminpghead{', repr(self.indent), '}{',
                             repr(self.pict_width), '}%\n')))
                self.fix_indent = True

                if leader is not None and not self.in_list:
                    self.in_list = True
                    self._backend.write(''.join(('\\grlisthead{', leader,
                                                 '}%\n')))

        if leader is None:
            self.emit('\n')
            self.emit('%s ' % self.fbeg)

        # TextDoc interface
    def end_paragraph(self):
        """End the current paragraph"""
        newline = '%\n\n'
        if self.in_list:
            self.in_list = False
            self.emit('\n\\grlisttail%\n')
            newline = ''
        elif self.in_table:
            newline = SEPARATION_PAT

        self.emit('%s%s' % (self.fend, newline))
        if self.fix_indent:
            self.emit('\\grminpgtail%\n\n')
            self.fix_indent = False

        if self.pict_width:
            self.pict_width = 0
            self.pict_height = 0

        # TextDoc interface
    def start_bold(self):
        """Bold face"""
        self.emit('\\textbf{')

        # TextDoc interface
    def end_bold(self):
        """End bold face"""
        self.emit('}')

        # TextDoc interface
    def start_superscript(self):
        self.emit('\\textsuperscript{')

        # TextDoc interface
    def end_superscript(self):
        self.emit('}')

        # TextDoc interface
    def start_table(self, name, style_name):
        """Begin new table"""
        self.in_table = True
        self.currow = 0

        # We need to know a priori how many columns are in this table
        styles = self.get_style_sheet()
        self.tblstyle = styles.get_table_style(style_name)
        self.numcols = self.tblstyle.get_columns()
        self.column_order = []
        for cell in range(self.numcols):
            self.column_order.append(cell)
        if self.get_rtl_doc():
            self.column_order.reverse()

        tblfmt = '*{%d}{l}' % self.numcols
        self.emit('\\begin{longtable}[l]{%s}\n' % (tblfmt), TAB_BEG)

        # TextDoc interface
    def end_table(self):
        """Close the table environment"""
        self.emit('%\n\\end{longtable}%\n', TAB_END)
        self.in_table = False

        # TextDoc interface
    def start_row(self):
        """Begin a new row"""
        self.emit('', ROW_BEG)
        # doline/skipfirst are flags for adding hor. rules
        self.doline = False
        self.skipfirst = False
        self.curcol = 0
        self.currow += 1

        # TextDoc interface
    def end_row(self):
        """End the row (new line)"""
        self.emit('\\\\ ')
        if self.doline:
            if self.skipfirst:
                self.emit(''.join((('\\cline{2-%d}' %
                                    self.numcols), '%\n')), ROW_END)
            else:
                self.emit('\\hline %\n', ROW_END)
        else:
            self.emit('%\n', ROW_END)
        self.emit('%\n')

        # TextDoc interface
    def start_cell(self, style_name, span=1):
        """Add an entry to the table.
        We always place our data inside braces
        for safety of formatting."""
        self.colspan = span
        self.curcol += self.colspan

        styles = self.get_style_sheet()
        self.cstyle = styles.get_cell_style(style_name)

#       ------------------------------------------------------------------
        # begin special modification for boolean values
        # values imported here are used for test '==1' and '!=0'. To get
        # local boolean values the tests are now transfered to the import lines
#       ------------------------------------------------------------------
        self.lborder = self.cstyle.get_left_border() == 1
        self.rborder = self.cstyle.get_right_border() == 1
        self.bborder = self.cstyle.get_bottom_border() == 1
        self.tborder = self.cstyle.get_top_border() != 0

        # self.llist not needed any longer.
        # now column widths are arranged in self.calc_latex_widths()
        # serving for fitting of cell contents at any column position.
        # self.llist = 1 == self.cstyle.get_longlist()

        cellfmt = "l"
        # Account for vertical rules
        if self.lborder:
            cellfmt = '|' + cellfmt
        if self.rborder:
            cellfmt = cellfmt + '|'

        # and Horizontal rules
        if self.bborder:
            self.doline = True
        elif self.curcol == 1:
            self.skipfirst = True
        if self.tborder:
            self.head_line = True
#       ------------------------------------------------------------------
#         end special modification for boolean values
#       ------------------------------------------------------------------

        self.emit('\\multicolumn{%d}{%s}' % (span, cellfmt), CELL_BEG, span)

        # TextDoc interface
    def end_cell(self):
        """Prepares for next cell"""
        self.emit('', CELL_END)

        # TextDoc interface
    def add_media(self, infile, pos, x, y, alt='', style_name=None, crop=None):
        """Add photo to report"""
        outfile = os.path.splitext(infile)[0]
        pictname = latexescape(os.path.split(outfile)[1])
        outfile = ''.join((outfile, '.jpg'))
        outfile2 = ''.join((outfile, '.jpeg'))
        outfile3 = ''.join((outfile, '.png'))
        if HAVE_PIL and infile not in [outfile, outfile2, outfile3]:
            try:
                curr_img = Image.open(infile)
                curr_img.save(outfile)
                width, height = curr_img.size
                if height > width:
                    y = y*height/width
            except IOError:
                self.emit(''.join(('%\n *** Error: cannot convert ', infile,
                                   '\n ***                    to ', outfile,
                                   '%\n')))
        elif not HAVE_PIL:
            from gramps.gen.config import config
            if not config.get('interface.ignore-pil'):
                from gramps.gen.constfunc import has_display
                if has_display() and self.uistate:
                    from gramps.gui.dialog import MessageHideDialog
                    title = _("PIL (Python Imaging Library) not loaded.")
                    message = _("Production of jpg images from non-jpg images "
                                "in LaTeX documents will not be available. "
                                "Use your package manager to install "
                                "python-imaging or python-pillow or "
                                "python3-pillow")
                    MessageHideDialog(title, message, 'interface.ignore-pil',
                                      parent=self.uistate.window)
            self.emit(''.join(('%\n *** Error: cannot convert ', infile,
                               '\n ***                    to ', outfile,
                               '\n *** PIL not installed %\n')))

        if self.in_table:
            self.pict_in_table = True

        self.emit(''.join(('\\grmkpicture{', outfile, '}{', repr(x), '}{',
                           repr(y), '}{', pictname, '}%\n')))
        self.pict_width = x
        self.pict_height = y

        # TextDoc interface
    def write_text(self, text, mark=None, links=False):
        """Write the text to the file"""
        links = True
        if text == '\n':
            text = ''
        text = latexescape(text)

        if links is True:
            text = re.sub(URL_PATTERN, _CLICKABLE, text)

        #hard coded replace of the underline used for missing names/data
        text = text.replace('\\_' * 13,
                            '\\underline{\\hspace{3\\grbaseindent}}')
        self.emit(text + ' ')


        # TextDoc interface
    def write_styled_note(self, styledtext, format, style_name,
                          contains_html=False, links=False):
        """
        Convenience function to write a styledtext to the latex doc.
        styledtext : assumed a StyledText object to write
        format : = 0 : Flowed, = 1 : Preformatted
        style_name : name of the style to use for default presentation
        contains_html: bool, the backend should not check if html is present.
            If contains_html=True, then the textdoc is free to handle that in
            some way. Eg, a textdoc could remove all tags, or could make sure
            a link is clickable. self ignores notes that contain html
        links: bool, make URLs clickable if True
        """
        links = True
        if contains_html:
            return
        text = str(styledtext)

        s_tags = styledtext.get_tags()
        if format:
            #preformatted, use different escape function
            self._backend.setescape(True)

        markuptext = self._backend.add_markup_from_styled(text, s_tags)

        if links is True:
            markuptext = re.sub(URL_PATTERN, _CLICKABLE, markuptext)

        #there is a problem if we write out a note in a table.
        # ..................
        # now solved by postprocessing in self.calc_latex_widths()
        # by explicitely setting suitable width for all columns.
        #
        if format:
            self.start_paragraph(style_name)
            self.emit(markuptext)
            self.end_paragraph()
            #preformatted finished, go back to normal escape function
            self._backend.setescape(False)
        else:
            for line in markuptext.split('%\n%\n '):
                self.start_paragraph(style_name)
                for realline in line.split('\n'):
                    self.emit(realline)
                    self.emit("~\\newline \n")
                self.end_paragraph()






class LateXDocOptions(LaTeXBaseDocOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        LaTeXBaseDocOptions.__init__(self, name)

    def add_menu_options(self, menu):
        """
        Add options to the document menu for the docgen.
        """
        LaTeXBaseDocOptions.add_menu_options(self,menu)

