from collections import defaultdict
import re
import os
import logging

log = logging.getLogger(__name__)

class Tool(object):
    def __init__(self, command_executor):
        self.executor = command_executor

    def process_line(self, dirname, line):
        """
        Processes a line return a 3-element tuple representing (filename,
        line_number, error_messages) or None to indicate no error.

        :param: dirname - directory the code is running in
        """
        raise NotImplementedError()

    def get_file_extensions(self):
        """
        Returns a list of file extensions this tool should run against.

        eg: ['.py', '.js']
        """
        raise NotImplementedError()

    def get_command(self, dirname):
        """
        Returns the command to run for linting. It is piped a list of files to
        run on over stdin.
        """
        raise NotImplementedError()

    def invoke(self, dirname, filenames=set()):
        """
        Main entrypoint for all plugins.
        
        Returns results in the format of:

        {'filename': {
          'line_number': [
            'error1',
            'error2'
            ]
          }
        }

        """
        retval = defaultdict(lambda: defaultdict(list))
        extensions = ' -o '.join(['-name "*.%s"' % ext for ext in
                                  self.get_file_extensions()])

        cmd = 'find %s %s | xargs %s' % (
            dirname, extensions, self.get_command())
        result = self.executor(cmd)
        for line in result.split('\n'):
            output = process_line(dirname, line)
            if output is not None:
                filename, lineno, messages = output
                retval[filename][lineno].append(messages)
        return retval

class JSHint(Tool):
    response_format = re.compile(r'^(?P<filename>.*): line (?P<line_number>\d+), col \d+, (?P<message>.*)$')
    jshintrc_filename = '.jshintrc'

    def process_line(self, dirname, line):
        line = line[len(dirname)+1:] # +1 for trailing slash to make relative dir
        match = self.response_format.search(line)
        if match is not None:
            return match.groups()

    def get_file_extensions(self):
        return ['.js']

    def get_command(self, dirname):
        cmd = "jshint "
        config_path = os.path.join(dirname, jshint_file)
        if os.path.exists(config_path):
            cmd += "--config=%s" % config_path
        return cmd


class PyLint(Tool):
    pylintrc_filename = '.pylintrc'

    def invoke(self, dirname, filenames=set()):
        to_return = defaultdict(lambda: defaultdict(list))
        log.debug("Running pylint on %s", dirname)
        cmd = 'find %s -name "*.py" | ' \
              'xargs pylint --output-format=parseable -rn'

        if os.path.exists(os.path.join(dirname, self.pylintrc_filename)):
            cmd += " --rcfile=%s" % os.path.join(
                dirname, self.pylintrc_filename)
        result = self.executor(cmd % dirname)
        # pylint is stupid, this should fix relative path linting
        # if repo is checked out relative to where imhotep is called.
        if os.path.abspath('.') in dirname:
            dirname = dirname[len(os.path.abspath('.'))+1:]

        # splitting based on newline + dirname and trailing slash will make
        # beginning of line until first colon the relative filename. It also has
        # the nice side effect of allowing us multi-line output from the tool
        # without things breaking.
        for line in result.split("\n%s/" % dirname):
            if len(line) == 0:
                continue
            filename, line_num, error = line.split(':', 2)
            if len(filenames) != 0 and filename not in filenames:
                continue
            to_return[filename][line_num].append(error)
        return to_return
