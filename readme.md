Doxygen filter for Squirrel
===========================

This is a doxygen filter to convert Squirrel scripts into something
that doxygen can convert into C++.   
It has been tested on Windows 7 with python 2.7.    
It was designed for Squirrel version 2.2 as used by OpenTTD for
AI and Game scripts.

Usage instructions
------------------
Set the following items in your doxygen config file.

1. EXTENSION_MAPPING: Add: nut=C++    
2. FILE_PATTERNS: Add: *.nut    
3. FILTER_PATTERS: Add either:    
    + \*.nut=doxygen\_squirrel\_filter.bat [or]    
    + \*.nut=doxygen\_squirrel\_filter.py    
For the first option you need to adapt the path to python in the batch
file.    
In case of the second option make sure that python is on your path and
that python is set for files with extension .py

Known problems
--------------
1. Functions need to be defined inside the class or they won't be
shown.    
It's not easy to fix this: we would have to parse the source twice.
First to find all the functions not defined inside the class and then
a second time to add them inside the class.    
Example: MailAI TownManager.nut
2. Inline code in the file outside of any function can confuse doxygen
too sometimes.    
Example: AILib.List main.nut the code at the bottom.
3. Multi line string constants not supported: (starting with @" ).

Copyright
---------
Copyright Jacob Boerema 2015.    
License: GPL version 2.
