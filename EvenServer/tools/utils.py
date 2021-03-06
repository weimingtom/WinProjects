#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import os


#主机定义
HOST_TYPE= \
{
	"Client"		:"C",
	"Gate"			:"G",
	"Zone"			:"Z",
	"Region" 		:"R",
	"Manager"		:"M",
	"Login"			:"L",
	"AIServer"		:"I",
	"Chat"		    :"H",
	"Stat"		    :"W",
	"Assistant"		:"A",
	"Admin"			:"D",
	"Supervisor"	:"V",
	"Daemon"		:"E",
	"Downtime"		:"O",
	"Friend"		:"F",
}
#主机关链定义
HOST_LINK= \
{
	"Client"		:["Client","Gate"],
	"Gate"			:["Gate"],
	"Zone"			:["Zone"],
	"Manager"		:["Manager"],
	"Login"			:["Login","Manager"],
	"AIServer"		:["AIServer"],
	"Chat"		    :["Chat"],
	"Stat"		   	:["Stat"],
	"Assistant"		:["Assistant"],
	"Admin"			:["Admin"],
	"Supervisor"		:["Supervisor"],
	"Daemon"		:["Daemon"],
	"Region"		:["Region"],
	"Downtime"		:["Downtime"],
	"Friend"			:["Friend"],
}
#主机活跃性分类(不活跃的主机与其相关协议号优先保留)
HOST_ACTIVITY= \
{
	"Client"				:True,
	"Gate"					:True,
	"Zone"					:True,
	"Manager"				:True,
	"AIServer"				:True,
	"Chat"		  			:True,
	"Stat"		  		 	:True,
	"Assistant"				:True,
	"Admin"					:False,
	"Supervisor"			:False,
	"Daemon"				:False,
	"Region"				:True,
	"Downtime"				:False,
	"Friend"				:True,
	"Login"				:True,
}


links={}
for k,v in HOST_LINK.items():
	for host in v:
		links[host]=0

HOST_LINK["None"] = ["Types"];
links["None"]=0
ALL_HOSTS=links.keys()

SEPARATOR_PACKET = "_"
SEPARATOR_HOST = ""
SEPARATOR_PROTO = "_"
SEPARATOR_ACTION = "_"

#动作类型
ACTION_TYPE= \
{
	"Request"		:"Req",
	"Acknowledge"	:"Ack",
	"Notify"		:"Ntf",
	"Broadcast"		:"Brd"
}

#tab字符填充
def tabStr(tabnum,format,*args):
	i=0
	f=""
	while i< tabnum:
		f += "\t"
		i += 1
	f += format
	return f % args

#从结点中获得字符
def getText(node,character="GBK"):
    rc = ""
    nodelist = node.childNodes
    for nod in nodelist:
        if nod.nodeType == nod.TEXT_NODE:
            rc = rc + nod.data
    return rc.encode(character)

def getAttr(node,name):
	return node.getAttribute(name).encode("GBK")

#调整字典值
def adjustDictValue(lst,new,old):
	#生成可用值字典
	i=1
	val={}
	while i < 60000:
		val[i]=0
		i += 1
	changed=0	#字典是否发生变化
	#删除不用的项
	old_items=old.items()
	for k, v in old_items:
		if new.has_key(k):
			try:
				del val[v]
			except KeyError:
				pass
			new[k]=v
		else:
			changed = 1
			
	#给新增的项赋值
	for i in lst:
		if new[i]<0:
			changed = 1
			new[i]=val.popitem()[0]

	val_key={}
	new_items=new.items()
	for k, v in new_items:
		val_key[v]=k
	return [changed,val_key]

#从结点中得到特定子元素集合
def getElements(node,name):
	res = []
	nodes = node.childNodes
	for nod in nodes:
		if nod.localName==name:
			res.append(nod)
	return res

#从结点中得到特定子元素
def getElement(node,name):
	res = []
	nodes = node.childNodes
	for nod in nodes:
		if nod.localName==name:
			return nod
	raise IndexError

#调整列表填充table
def fillTabs(data):
	height = len(data)
	width = 0
	i = 0	
	while i < height:
		if type(data[i])==list:
			width = len(data[i])
			break
		i += 1

	i = 0
	while i < width-1:
		maxlen = 0
		j = 0
		while j < height:
			strdata = data[j][i*2]
			if len(strdata)>maxlen:
				maxlen = len(strdata)
			j += 1
		tabmun = maxlen/4 + 1
		maxlen = tabmun*4
		j = 0 
		while j < height:
			if type(data[j])==list:
				strdata = data[j][i*2]
				tabfixnum = tabmun - ( len(strdata) / 4 )
				data[j].insert(i*2+1,tabfixnum)
			j += 1
		i += 1
	return width

#tab字符填充数据块
def tabData(tabnum,data):
	width=fillTabs(data)*2-1
	res = ""
	for line in data:
		if type(line)==list:
			res += tabStr(tabnum,"%s",line[0])
			i = 1
			while i < width:
				res += tabStr(line[i],"%s",line[i+1])
				i +=2
			res += "\n"
		else:
			res += "%s\n" % line
	return res

#得到所关链的主机
def getHostLink(fr,to):
	fr_hosts=fr.split(",")
	to_hosts=to.split(",")
	link={}
	for f in fr_hosts:
		for host in HOST_LINK[f]:
			link[host]=0
	for t in to_hosts:
		for host in HOST_LINK[t]:
			link[host]=0
	fr = fr_hosts[0]
	to = to_hosts[0]
	return [fr_hosts[0],to_hosts[0],link.keys()]

#初始化hosts字典
def initHostDict(dic,val):
	for host in ALL_HOSTS:
		if type(val)==list:
			dic[host]=[]
		elif type(val)==dict: 
			dic[host]={}
		else:
			dic[host]=val

#是否需要更新文件
def needUpdateFile(filename,content):
	try:
		return os.read(os.open(filename,os.O_RDONLY),100000000)!=content
	except OSError , e:
		if e[0]==2:
			return 1
		else:
			raise e
			
#从长文件名中提取去除路径和后缀的基本名
def GetFileBaseName(filename) :
	begin = max(filename.rfind('\\'), filename.rfind('/'))
	begin += 1
	end = filename.rfind('.')
	if end < begin :
		end = len(filename)
	return filename[begin : end]









