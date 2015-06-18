#!/usr/bin/env python
# -*- coding: utf-8 -*-	
#
# This is a filter to convert Squirrel (*.nut) scripts
# into something doxygen can understand.
# Copyright (C) 2015  Jacob Boerema
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# ------------------------------------------------------------------------- 

## @file doxygen_squirrel_filter.py Filter for Squirrel to make doxygen understand it as C++.

## @author Jacob Boerema
## @date 2015
## @version 1.0
## @copyright GPL version 2

## Instructions.
## -------------
## Set the following items in your doxygen config file
## 1. EXTENSION_MAPPING: Add: nut=C++
## 2. FILE_PATTERNS: Add: *.nut
## 3. FILTER_PATTERS: Add:
## + *.nut=doxygen_squirrel_filter.bat [or]
## + *.nut=doxygen_squirrel_filter.py
## For the first option you need to adapt the path to python in the batch file.
## In case of the second option make sure that python is on your path and that
## python is set for files with extension .py

## Known problems:
## ---------------
## 1. Functions need to be defined inside the class or they won't be shown.
## It's not easy to fix this: we would have to parse the source twice. First to find all the
## functions not defined inside the class and then a second time to add them inside the class.
## Example: MailAI TownManager.nut
## 2. Inline code in the file outside of any function can confuse doxygen too sometimes
## Example: AILib.List main.nut the code at the bottom.
## 3. Multi line string constants not supported: (starting with @" ). Note multi line string
## constants also support " inside them by writing ""


# First version: 2015-06-15/17
# Tested on Windows 7 with Squirrel version 2.2 as used by OpenTTD for AI and game scripts.

# --------------------------------------------------------------
# Settings that can be changed by the user of our doxygen filter
# --------------------------------------------------------------

## Do we want to keep function or replace it with ""
keep_function = True;

## Do we want to keep constructor or replace it with ""
keep_constructor = True;

## Check for "}" at end of class definition and add a ";"if it's not there.
## You can speed up filtering by turning this off if you always add a ";" yourself
check_end_of_class = True;

# --------------------------------------------------------------

# Import some libraries that we need.
import os
import io
import sys
import re


## Turn debugging info printing on or off
print_debug_info = False;

# constants
MAX_POS_ON_LINE = 999999;


## Print a string to stderr
def alwaysprint(string):
	sys.stderr.write(string);

## SquirrelFilter is our class to convert Squirrel scripts to something doxygen can understand.
class SquirrelFilter:

	# ----------------------------------
	# Class Variables.
	# ----------------------------------

	## doxygen reads data from stdout so that's where we are going to send our filtered output.
	outfile = sys.stdout;

	## Keep track of being in a multi line comment or not
	in_multiline_comment = False;

	## Keep track of the last seen class name
	current_class = "";

	## Determines if we are looking for a class definition block: "{"
	want_class_start = False;
	
	## Determines if we are looking for end of class "}"
	want_class_end = False;

	## Determines at what level we are in the code blocks hierarchy needed to find end of class.
	block_level = 0;

	# ----------------------------------

	# regular expressions

	# 1. Comments and string constants
	re_multiline_comment_start = re.compile("\/[*]");
	re_multiline_comment_end = re.compile("[*]\/");
	re_singleline_comment = re.compile("\/\/");

	## The following regular expression confuses doxygen's inbuilt python parser.
	## Any code documentation starting with this and anything below it will be ignored.
	## re_string = re.compile('"');
	## Work around doxygen problem described above
	double_quote = '"';
	re_string = re.compile(double_quote);

	# 2. Squirrel language constructs that need changing
	re_assignment = re.compile("<-");
	re_extends = re.compile("extends");
	re_require = re.compile("require\s*\(");
	re_import = re.compile("import\s*\(");

	# Maybe keep function and constructor. Even though doxygen will think its the function result
	# it might look nice in the documentation to see those Squirrel names.
	# Or make it a variable that can be set whether to remove it or not.
	re_constructor = re.compile("constructor");
	re_function = re.compile("function");

	# TODO:
	# Support comments /* public: */ and /* private: */ and change it to keywords public: and private:
	# Same for static?

	# 3. Squirrel elements we need to find
	re_blockstart = re.compile("\{");
	re_blockend = re.compile("\}");
	re_classend = re.compile("\s*;");
	re_classname = re.compile("\s*class\s+([a-zA-Z_]+[a-zA-Z_0-9]*)")

	def __init__(self, filename):
		self.filename = filename;

	## Print a string to stderr if print_debug_info is True
	def debugprint(self, string):
		#global print_debug_info
		if (print_debug_info):
			sys.stderr.write(string);

	## Determine if the first match is a multi line comment, single line comment or string start
	def first_match(self, ml_comment, sl_comment, str_start):
		if (ml_comment is None and sl_comment is None and str_start is None):
			self.debugprint("....... All None");
			return None;
		if (ml_comment is None):
			self.debugprint("....... No multi line");
			pos_ml = MAX_POS_ON_LINE;
		else:
			pos_ml = ml_comment.start();
			if (pos_ml is None):
				pos_ml = MAX_POS_ON_LINE;
		if (sl_comment is None):
			self.debugprint("....... No single line");
			pos_sl = MAX_POS_ON_LINE;
		else:
			pos_sl = sl_comment.start();
			if (pos_sl is None):
				pos_sl = MAX_POS_ON_LINE;
		if (str_start is None):
			self.debugprint("....... No string");
			pos_str = MAX_POS_ON_LINE;
		else:
			pos_str = str_start.start();
			if (pos_str is None):
				pos_str = MAX_POS_ON_LINE;
		if (pos_ml < pos_sl and pos_ml < pos_str):
			return ml_comment;
		elif (pos_sl < pos_ml and pos_sl < pos_str):
			return sl_comment;
		else:
			return str_start;

	## Checks if we have arrived at the end of class.
	def check_end_of_class(self, part):
		# For now we hardcode end of class level at level 0
		if (self.block_level == 0 and self.want_class_end == True):
			# Check if a ";" follows, if not add it or doxygen can get somewhat confused.
			classend = self.re_classend.match(part);
			if (classend is None):
				# No ";" so add it.
				part = ";" + part;
				self.want_class_end = False;
				self.debugprint("<end of class>");
		return part;
	
	## Parse "{" and "}" to keep track of the code level.
	def parse_blocks(self, part):
		output = "";
		while (True):
			blockstart = self.re_blockstart.search(part);
			blockend = self.re_blockend.search(part);
			if blockstart and blockend:
				# both available, determine which comes first
				if (blockstart.start() < blockend.start()):
					# block start comes first: increase level
					self.block_level += 1;
					self.debugprint("*** " + str(self.block_level) + " ***");
					output += part[:blockstart.end()];
					part = part[blockstart.end():];
				else:
					# block end comes first: decrease level
					self.block_level -= 1;
					self.debugprint("*** " + str(self.block_level) + " ***");
					output += part[:blockend.end()];
					part = self.check_end_of_class(part[blockend.end():]);
			elif blockstart:
				# Only start of block available: increase block level
				self.block_level += 1;
				self.debugprint("*** " + str(self.block_level) + " ***");
				output += part[:blockstart.end()];
				part = part[blockstart.end():];
			elif blockend:
				# Only end of block available: decrease block level
				self.block_level -= 1;
				self.debugprint("*** " + str(self.block_level) + " ***");
				output += part[:blockend.end()];
				part = self.check_end_of_class(part[blockend.end():]);
			else:
				output += part;
				break;
		return output;

	## Filter the string part and return in output.
	## Note that we currently only allow one of each element on a line.
	def filter_part(self, part):
		output = part;
		start_pos = 0;
		
		# Replace <- with =
		assignment = self.re_assignment.search(output);
		if (assignment is not None):
			output = output[:assignment.start()] + "=" + output[assignment.end():]
		else:
			output = part;

		# Replace extends with :
		extends = self.re_extends.search(output);
		if (extends is not None):
			output = output[:extends.start()] + ":" + output[extends.end():]

		# Get class name if a class is defined
		classname = self.re_classname.match(output);
		if classname:
			self.want_class_start = True;
			start_pos = classname.end();
			self.current_class = classname.group(1);
			alwaysprint("class " + self.current_class + "\n");
		
		# Check if we can find a class start block
		if self.want_class_start:
			first_part = output[:start_pos];
			last_part = output[start_pos:];
			class_start = self.re_blockstart.search(last_part);
			if class_start:
				self.want_class_start = False;
				self.want_class_end = True;
				output = first_part + last_part[:class_start.end()] + "public:" + last_part[class_start.end():];

		# Replace constructor with the class name
		constr = self.re_constructor.search(output);
		if constr:
			if (keep_constructor == False):
				output = output[:constr.start()] + self.current_class + output[constr.end():];
			else:
				output = output[:constr.end()] + " " + self.current_class + output[constr.end():];
				
		if (keep_function == False):
			# Replace function with nothing
			temp = self.re_function.search(output);
			if temp:
				output = output[:temp.start()] + output[temp.end():];

		temp = self.re_require.search(output);
		if temp:
			# Found require, replace by #include. We don't bother with the closing ")" since it seems doxygen doesn't care.
			output = output[:temp.start()] + "#include " + output[temp.end():];
		temp = self.re_import.search(output);
		if temp:
			# Found import, replace by #include. We don't bother with the closing ")" since it seems doxygen doesn't care.
			output = output[:temp.start()] + "#include " + output[temp.end():];

		if check_end_of_class:
			output = self.parse_blocks(output);

		return output

	## Handle one line of text and send to stdout after filtering.
	def line_handler(self, line, lineno):
		start_pos = 0;
		temp_line = line[start_pos:]
		outline = "";

		while(True):
			if (self.in_multiline_comment):
				ml_end = self.re_multiline_comment_end.search(temp_line);
				if (ml_end is None):
					# End of multi line comment not found on this line
					outline += temp_line;
					break;
				else:
					# End of multi line comment found
					self.in_multiline_comment = False;
					outline += temp_line[:ml_end.end()];
					temp_line = temp_line[ml_end.end():];
			else:
				ml_start = self.re_multiline_comment_start.search(temp_line);
				sl_start = self.re_singleline_comment.search(temp_line);
				str_start = self.re_string.search(temp_line);
				next_match = self.first_match(ml_start, sl_start, str_start);
				if next_match is None:
					outline += self.filter_part(temp_line);
					break;
				elif next_match == ml_start:
					self.in_multiline_comment = True;
					# Filter part before the multi line comment starts and add to output
					outline += self.filter_part(temp_line[:ml_start.end()]);
					temp_line = temp_line[ml_start.end():];
				elif next_match == sl_start:
					# First filter the part before the comment starts, then add the comment itself unfiltered
					outline += self.filter_part(temp_line[:sl_start.start()]);
					outline += temp_line[sl_start.start():];
					break;
				else:
					# Filter the part before the string starts and add to output
					outline += self.filter_part(temp_line[:str_start.start()]);
					# Then try to find the end of string
					temp_line = temp_line[str_start.start():]
					str_end = self.re_string.search(temp_line);
					if (str_end is None):
						#Error
						alwaysprint("** Warning: didn't find end of string on line" + str(lineno+1));
						# Add the string contents to output
						outline += temp_line;
						break;
					else:
						# Add the string contents to output
						outline += temp_line[:str_end.end()];
						temp_line = temp_line[str_end.end():]
		self.debugprint(outline);
		#alwaysprint(outline);
		return outline
	
	## Filter the file and output to stdout
	def filter(self):
		self.outfile = sys.stdout;

		# Open file for reading and writing (r+)
		nut_file = io.open(self.filename, "r+", newline='', encoding='utf-8')   # newline='' means don't convert line endings
		lines = nut_file.readlines();
		nut_file.seek(0);

		for i, line in enumerate(lines):
			try:
				self.outfile.write(self.line_handler(line, i));
			except UnicodeEncodeError,e:
				alwaysprint("*** Unicode encoding error on line " + str(i+1) + "!\n");

		# Close our file
		nut_file.close();

# --------------------------------------------------------------------------------------------------
## This is our main function. We check for correct arguments here and then start our filter.
# --------------------------------------------------------------------------------------------------
alwaysprint("Starting doxygen Squirrel filter.\n")

if len(sys.argv) != 2:
	alwaysprint("usage: " + sys.argv[0] + " filename");
	sys.exit(1);


# Filter the specified file and print the result to stdout
filename = sys.argv[1] ;

alwaysprint("Filtering file " + filename + ".\n")

DoxygenFilter = SquirrelFilter(filename);
DoxygenFilter.filter();

sys.exit(0);
