# coding:utf-8

import sys
import io
import os
import time
import subprocess
import json

sys.path.append(os.getcwd() + "/class/core")
import public


app_debug = False
if public.isAppleSystem():
    app_debug = True


def getPluginName():
    return 'op_waf'


def getPluginDir():
    return public.getPluginDir() + '/' + getPluginName()


def getServerDir():
    return public.getServerDir() + '/' + getPluginName()


def getArgs():
    args = sys.argv[2:]
    tmp = {}
    args_len = len(args)

    if args_len == 1:
        t = args[0].strip('{').strip('}')
        t = t.split(':')
        tmp[t[0]] = t[1]
    elif args_len > 1:
        for i in range(len(args)):
            t = args[i].split(':')
            tmp[t[0]] = t[1]

    return tmp


def checkArgs(data, ck=[]):
    for i in range(len(ck)):
        if not ck[i] in data:
            return (False, public.returnJson(False, '参数:(' + ck[i] + ')没有!'))
    return (True, public.returnJson(True, 'ok'))


def getConf():
    path = public.getServerDir() + "/openresty/nginx/conf/nginx.conf"
    return path


def initDomainInfo():
    data = []
    path_domains = getJsonPath('domains')

    _list = public.M('sites').field('id,name,path').where(
        'status=?', ('1',)).order('id desc').select()

    for i in range(len(_list)):
        tmp = {}
        tmp['name'] = _list[i]['name']
        tmp['path'] = _list[i]['path']

        _list_domain = public.M('domain').field('name').where(
            'pid=?', (_list[i]['id'],)).order('id desc').select()

        tmp_j = []
        for j in range(len(_list_domain)):
            tmp_j.append(_list_domain[j]['name'])

        tmp['domains'] = tmp_j
        data.append(tmp)
    cjson = public.getJson(data)
    public.writeFile(path_domains, cjson)


def initSiteInfo():
    data = []
    path_domains = getJsonPath('domains')
    path_site = getJsonPath('site')

    domain_contents = public.readFile(path_domains)
    domain_contents = json.loads(domain_contents)

    try:
        site_contents = public.readFile(path_site)
    except Exception as e:
        site_contents = "{}"

    site_contents = json.loads(site_contents)

    for x in range(len(domain_contents)):
        name = domain_contents[x]['name']

        if name in site_contents:
            pass
        else:
            tmp = {}
            tmp['cdn'] = False
            tmp['log'] = True
            tmp['get'] = True
            tmp['post'] = True
            tmp['open'] = False
            site_contents[name] = tmp

    cjson = public.getJson(site_contents)
    public.writeFile(path_site, cjson)


def status():
    initDomainInfo()
    initSiteInfo()

    path = getConf()
    if not os.path.exists(path):
        return 'stop'

    conf = public.readFile(path)
    if conf.find("#include luawaf.conf;") != -1:
        return 'stop'
    if conf.find("luawaf.conf;") == -1:
        return 'stop'
    return 'start'


def contentReplace(content):
    service_path = public.getServerDir()
    waf_path = public.getServerDir() + "/openresty/nginx/conf/waf"
    content = content.replace('{$ROOT_PATH}', public.getRootDir())
    content = content.replace('{$SERVER_PATH}', service_path)
    content = content.replace('{$WAF_PATH}', waf_path)
    return content


def initDreplace():

    config = getPluginDir() + '/waf/config.json'
    content = public.readFile(config)
    content = json.loads(content)
    content['reqfile_path'] = public.getServerDir(
    ) + "/openresty/nginx/conf/waf/html"
    public.writeFile(config, public.getJson(content))

    path = public.getServerDir() + "/openresty/nginx/conf"
    if not os.path.exists(path + '/waf'):
        sdir = getPluginDir() + '/waf'
        cmd = 'cp -rf ' + sdir + ' ' + path
        public.execShell(cmd)

    config = public.getServerDir() + "/openresty/nginx/conf/waf/lua/init.lua"
    content = public.readFile(config)
    content = contentReplace(content)
    public.writeFile(config, content)

    waf_conf = public.getServerDir() + "/openresty/nginx/conf/luawaf.conf"
    waf_tpl = getPluginDir() + "/conf/luawaf.conf"
    content = public.readFile(waf_tpl)
    content = contentReplace(content)
    public.writeFile(waf_conf, content)


def start():
    initDreplace()

    path = getConf()
    conf = public.readFile(path)
    conf = conf.replace('#include luawaf.conf;', "include luawaf.conf;")

    public.writeFile(path, conf)
    public.restartWeb()
    return 'ok'


def stop():
    path = public.getServerDir() + "/openresty/nginx/conf/waf"
    if os.path.exists(path):
        cmd = 'rm -rf ' + path
        public.execShell(cmd)

    path = getConf()
    conf = public.readFile(path)
    conf = conf.replace('include luawaf.conf;', "#include luawaf.conf;")

    public.writeFile(path, conf)
    public.restartWeb()
    return 'ok'


def restart():
    public.restartWeb()
    return 'ok'


def reload():
    stop()
    public.execShell('rm -rf ' + public.getServerDir() +
                     "/openresty/nginx/logs/error.log")
    start()
    return 'ok'


def getJsonPath(name):
    path = public.getServerDir() + "/openresty/nginx/conf/waf/" + name + ".json"
    return path


def getRuleJsonPath(name):
    path = public.getServerDir() + "/openresty/nginx/conf/waf/rule/" + name + ".json"
    return path


def getRule():
    args = getArgs()
    data = checkArgs(args, ['rule_name'])
    if not data[0]:
        return data[1]

    rule_name = args['rule_name']
    fpath = getRuleJsonPath(rule_name)
    content = public.readFile(fpath)
    return public.returnJson(True, 'ok', content)


def setObjStatus():
    args = getArgs()
    data = checkArgs(args, ['obj', 'statusCode'])
    if not data[0]:
        return data[1]

    conf = getJsonPath('config')
    content = public.readFile(conf)
    cobj = json.loads(content)

    o = args['obj']
    status = args['statusCode']
    cobj[o]['status'] = status

    cjson = public.getJson(cobj)
    public.writeFile(conf, cjson)
    return public.returnJson(True, '设置成功!')


def setRetry():
    args = getArgs()
    data = checkArgs(args, ['retry', 'retry_time',
                            'retry_cycle', 'is_open_global'])
    if not data[0]:
        return data[1]

    conf = getJsonPath('config')
    content = public.readFile(conf)
    cobj = json.loads(content)

    cobj['retry'] = args

    cjson = public.getJson(cobj)
    public.writeFile(conf, cjson)

    return public.returnJson(True, '设置成功!', [])


def setSiteRetry():
    return public.returnJson(True, '设置成功!', [])


def saveScanRule():

    args = getArgs()
    data = checkArgs(args, ['header', 'cookie', 'args'])
    if not data[0]:
        return data[1]

    conf = getRuleJsonPath('scan_black')
    content = public.readFile(conf)
    cobj = json.loads(content)

    cobj['retry'] = args

    cjson = public.getJson(cobj)
    public.writeFile(conf, cjson)

    return public.returnJson(True, '设置成功!', [])


def setObjOpen():
    args = getArgs()
    data = checkArgs(args, ['obj'])
    if not data[0]:
        return data[1]

    conf = getJsonPath('config')
    content = public.readFile(conf)
    cobj = json.loads(content)

    o = args['obj']
    if cobj[o]["open"]:
        cobj[o]["open"] = False
    else:
        cobj[o]["open"] = True

    cjson = public.getJson(cobj)
    public.writeFile(conf, cjson)
    return public.returnJson(True, '设置成功!')


def getWafSrceen():
    conf = getJsonPath('total')
    return public.readFile(conf)


def getWafConf():
    conf = getJsonPath('config')
    return public.readFile(conf)


def getWafSite():
    return ''


if __name__ == "__main__":
    func = sys.argv[1]
    if func == 'status':
        print status()
    elif func == 'start':
        print start()
    elif func == 'stop':
        print stop()
    elif func == 'restart':
        print restart()
    elif func == 'reload':
        print reload()
    elif func == 'conf':
        print getConf()
    elif func == 'get_rule':
        print getRule()
    elif func == 'set_obj_status':
        print setObjStatus()
    elif func == 'set_obj_open':
        print setObjOpen()
    elif func == 'set_retry':
        print setRetry()
    elif func == 'set_site_retry':
        print setSiteRetry()
    elif func == 'save_scan_rule':
        print saveScanRule()
    elif func == 'waf_srceen':
        print getWafSrceen()
    elif func == 'waf_conf':
        print getWafConf()
    elif func == 'waf_site':
        print getWafSite()
    else:
        print 'error'