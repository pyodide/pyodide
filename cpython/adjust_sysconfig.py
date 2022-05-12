import os
import pprint

def load_sysconfig(sysconfig_name):
    _temp = __import__(sysconfig_name, globals(), locals(), ['build_time_vars'], 0)
    config_vars = _temp.build_time_vars
    return config_vars, _temp.__file__

def write_sysconfig(destfile, config_vars):
    with open(destfile, 'w', encoding='utf8') as f:
        f.write('# system configuration generated and used by'
                ' the sysconfig module\n')
        f.write('build_time_vars = ')
        pprint.pprint(config_vars, stream=f)

def adjust_sysconfig(config_vars):
    config_vars["CC"] = "cc"
    config_vars["CXX"] = "c++"


if __name__ == "__main__":
    sysconfig_name = os.environ["SYSCONFIG_NAME"]
    config_vars, file = load_sysconfig(sysconfig_name)
    adjust_sysconfig(config_vars)
    write_sysconfig(file, config_vars)

