# r6StatParser
This a script made to parse the JSON output produced by r6-dissect.

Some wierd band-aid behavior has to be taken due to some inconsistent output from r6-dissect.
I don't expect this to be the most well coded thing I've ever created beacuse of this

I run this with python 3.13.7

Get the latest version of r6-dissect here: https://github.com/redraskal/r6-dissect/releases

You'll need the jsonpath-ng library to run this script

pip install jsonpath-ng==1.7.0

Command to run the script

py R6StatParser.py <json_file_from_r6_dissect>

jsonpath 1.8.0 does not have 'path.index'. either use 1.7.0 or replace the lines that have errors with 'path.indicies[0]'
