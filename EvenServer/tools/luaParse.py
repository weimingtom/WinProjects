#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import xml.dom.minidom
import os
import re
import glob
from utils import *
from config import *

#载入原先的数据定义
import sys
sys.path.append(PATH_PROTO_SOURCE)
try:
	from cmd_def import *
except ImportError:
	sys.exit(0)
try:
	from err_def import *
except ImportError:
	sys.exit(0)

#触发器函数
trigger_function=""
#触发器注册
trigger_register=""
#消息解析函数
parse_function=""
#常量定义
const_vars=""
#常量定义
alias_types=""

#当前命令定义

def handleProto(proto):
	handleTypes(getElement(proto,"Types"))
	#消息处理
	messages=getElements(getElement(proto,"Messages"),"Message")
	for message in messages:
		handleMessage(message)

def handleMessage(message):
	descs=getText(getElement(message,"Description")).split("\n");
	name=getText(getElement(message,"Name"))
	type=getText(getElement(message,"Type"))
	fr_hosts=getText(getElement(message,"From")).replace("\n",",")
	to_hosts=getText(getElement(message,"To")).replace("\n",",")
	hosts_info=getHostLink(fr_hosts,to_hosts)
	fr=hosts_info[0]
	to=hosts_info[1]
	global trigger_function
	global trigger_register
	cmd = HOST_TYPE[fr] + SEPARATOR_HOST + HOST_TYPE[to] + SEPARATOR_PROTO + name.upper() + SEPARATOR_ACTION + ACTION_TYPE[type].upper()
	p_name = "P" + SEPARATOR_PACKET + HOST_TYPE[fr] + SEPARATOR_HOST + HOST_TYPE[to] + SEPARATOR_PROTO + name + SEPARATOR_ACTION + ACTION_TYPE[type]

	#触发器注册
	try:
		trigger_register+=tabStr(1,"TriggerRegisterParserMsgEvent(\"on%s\",\"parse_%d\",%d);\n",cmd,CMDS[cmd],CMDS[cmd])
	except KeyError:
		print "Can't find %s" % cmd
		sys.exit(0)
	#触发器函数
	trigger_function+=tabStr(0,"on%s_Conditions=True;\n",cmd);
	trigger_function+=tabStr(0,"function on%s_Actions()\n",cmd);
	trigger_function+=tabStr(1,"Action(\"%s\",\"%s\",parse%s);\n",p_name,"%s\\n%s->%s" % (descs[0],fr_hosts,hosts_info),p_name);
	trigger_function+=tabStr(0,"end\n\n");
	#解析函数
	handleMembers(getElement(message,"Content"),p_name)

def expandName(type_name,sub_types):
	if sub_types.has_key(type_name):
		return sub_types[type_name]
	else:
		return type_name


def pyParseTypeName(type_name,sub_types):
	#std::vector<class>
	if type_name[0:11]=="std_vector_" and type_name[-1:]=="_":
		#vector形式，不可能处在in_union方式下,不支持多重vector
		type_name=expandName(type_name[11:-1],sub_types)
		return ["parseVector", [ "parse%s" % type_name ] ]
	elif type_name[0:14]=="Zoic_VarArray_" and type_name[-1:]=="_":
		#Array形式，不可能处在in_union方式下,不支持多重Array
		type_name=type_name[14:-1].split(",")[0]
		type_name=expandName(type_name,sub_types)
		return ["parseVarArray", [ "parse%s" % type_name ] ]
	elif type_name[0:14]=="Zoic_FixArray_" and type_name[-1:]=="_":
		splitParams = type_name[14:-1].split(",")
		count_name = splitParams[1]
		type_name=expandName(splitParams[0],sub_types)
		return ["parseFixArray", [ "parse%s" % type_name,count_name ] ]
	elif type_name[0:12]=="Zoic_String_" and type_name[-1:]=="_":
		#String形式，不可能处在in_union方式下
		return ["parseString", [] ]
	elif type_name[0:12]=="Zoic_Binary_" and type_name[-1:]=="_":
		#Binary形式，不可能处在in_union方式下
		return ["parseBinary", [] ]
	return ["parse%s" % type_name, [] ]


#处理结构或联合内成员列表
def handleMembers(node,t_name,top=1,types=None,names=None,descs=None,conds=None,s_types=None):
	#(结点,类型名称,是否顶层协议,成员类型列表,成员名称列表,成员描述列表,成员条件列表,子类型定义)
	members=getElements(node,"Member")
	if types is None:
		types=[]	#类型列表
	if names is None:
		names=[]	#名称列表
	if conds is None:
		conds=[]	#条件列表
	if descs is None:
		descs=[]	#描述列表
	sub_types={}	#在本层命名空间中的子类型定义
	if s_types is not None:
		#将上层空间定义引入到本层
		s_items=s_types.items()
		for k,v in s_items:
			sub_types[k]=v
	enums=[]	#枚举值列表
	for member in members:
		handleMember(member,types,names,descs,conds,enums,t_name,sub_types)

	#将相邻的相同条件合并在一起
	name_conds=[]	#[条件,[类型,名称,描述]]
	names_len = len(names)
	if names_len >0:
		name_cond= []
		name_cond.append(conds[0])
		name_cond.append([[types[0],names[0],descs[0]]])
		cur_cond=conds[0]
		i=1
		while i < names_len:
			if conds[i]==cur_cond:
				name_cond[1].append([types[i],names[i],descs[i]])
			else:
				name_conds.append(name_cond)
				name_cond = []
				name_cond.append(conds[i])
				name_cond.append([[types[i],names[i],descs[i]]])
				cur_cond=conds[i]
			i += 1
		name_conds.append(name_cond)

	#将变量名称与值设为合适的值
	for name_cond in name_conds:
		for enum in enums:
			name_cond[0]=name_cond[0].replace(enum,t_name+"_"+enum)
		name_cond[0]=adjustCondition(names,name_cond[0])
		name_cond[0]=name_cond[0].replace("||"," or ")
		name_cond[0]=name_cond[0].replace("&&"," and ")
		name_cond[0]=name_cond[0].replace("!=","~=")

	#自动生成解析代码
	if node.localName!="Union":
		global parse_function
		#code 当前类型代码
		if top:
			code = tabStr(0,"function parse%s(parent)\n",t_name)
		else:
			code = tabStr(0,"function parse%s(parent,name,desc)\n",t_name)
			code += tabStr(1,"parent=makeStructNode(parent,name,desc);\n")
		code += tabStr(1,"local res={};\n")
		in_union=0
		for name_cond in name_conds:
			if name_cond[0]!="":
				have_if=1
				nametab=2
			else:
				have_if=0
				nametab=1
			if have_if:
				code += tabStr(1,"if (%s) then\n",name_cond[0])
			for item in name_cond[1]:
				if item[0]=="?U+":		#联合开始
					union_name=item[1]
					in_union=1
					code += tabStr(nametab,"res.%s={};\n",union_name);
					code += tabStr(nametab,"local uNode=makeStructNode(parent,\"%s\",\"%s\");\n",union_name,item[2]);
				elif item[0]=="?U-":	#联合结束
					in_union=0
				else:
					type_name=item[0]	#类型名
					#将类型扩展为真正的名称
					type_name=expandName(type_name,sub_types)
					typeNameOutput = pyParseTypeName(type_name,sub_types)
					py_paramcontent = ""
					for paramname in typeNameOutput[1]:
						py_paramcontent += ","
						py_paramcontent += paramname
					if in_union:
						code += tabStr(nametab,"res.%s.%s=%s(uNode,\"%s\",\"%s\"%s);\n",union_name,item[1],typeNameOutput[0],item[1],item[2],py_paramcontent);
					else:
						code += tabStr(nametab,"res.%s=%s(parent,\"%s\",\"%s\"%s);\n",item[1],typeNameOutput[0],item[1],item[2],py_paramcontent);
			if have_if:
				code += tabStr(1,"end\n")
		code += tabStr(1,"return res;\n")
		code += tabStr(0,"end\n\n")
		parse_function += code

#调整单词
def adjustWord(names,word):
	result = word
	for name in names:
		if word==name:
			result="res."+word
			break
	return result

#调整条件
def adjustCondition(names,condition):
	word=""
	index=0
	result=""
	length=len(condition)
	while index < length:
		ch = condition[index:index+1]
		if ch.isalnum() or ch =="_":
			word+=ch
		else:
			#单词结束
			if word!="":
				result+=adjustWord(names,word)
			result+=ch
			word=""
		index +=1
	if word!="":
		result+=adjustWord(names,word)
	return result

def transferTypeName(code_typename):
	return code_typename.replace("::","_").replace("<","_").replace(">","_").replace(" ","_").replace("*","_")

def handleMember(node,types,names,descs,conds,enums,t_name,s_types):
	#类型定义
	typenode=node.firstChild
	while not typenode.hasChildNodes():
		typenode=typenode.nextSibling
	tagName=typenode.localName
	type_name = ""
	if tagName=="Type":
		type_name=getText(typenode)
	elif tagName=="Struct":
		type_name=handleStruct(typenode,t_name,s_types)
	elif tagName=="Union":
		u_types=[]	#联合内的成员类型定义
		u_names=[]	#联合内的成员名称定义
		u_conds=[]	#联合内的条件定义
		u_descs=[]	#联合内的成员描述
		handleUnion(typenode,t_name,u_types,u_names,u_descs,u_conds,s_types)
	elif tagName=="Enum":
		global const_vars
		_enums=[]
		res=handleEnum(typenode,_enums)
		i=0
		data=[]
		for enum in _enums:
			data.append([t_name+"_"+enum,"=%d;" % i])
			i +=1
			enums.append(enum)
		const_vars+=tabData(0,data)
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	try:
		_descs = getText(getElement(node,"Description")).split("\n")
	except IndexError:
		_descs = [""]
	try:
		condition = getText(getElement(node,"Condition"))
	except IndexError:
		condition = ""

	#名称
	if name!="":
		if tagName=="Union":
			u_names_len=len(u_names)
			i = 0
			names.append(name)
			conds.append("")
			types.append("?U+")
			descs.append(_descs[0])
			while i < u_names_len:
				names.append(u_names[i])
				conds.append(u_conds[i])
				types.append(u_types[i])
				descs.append(u_descs[i])
				i += 1
			names.append(name)
			conds.append("")
			types.append("?U-")
			descs.append("")
		else:
			names.append(name)
			conds.append(condition)
			types.append( transferTypeName(type_name) )
			descs.append(_descs[0])

def handleStruct(node,p_name,s_types=None):
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	if p_name!="":
		if s_types is not None:
			s_types[name]=p_name+"_"+name
		name=p_name+"_"+name
	handleMembers(node,name,0,None,None,None,None,s_types)
	return name

def handleUnion(node,p_name,types=None,names=None,descs=None,conds=None,s_types=None):
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	if p_name!="":
		name=p_name+"_"+name
	handleMembers(node,name,0,types,names,descs,conds,s_types)

def handleTypes(types):
	for node in types.childNodes:
		if node.hasChildNodes():
			tagName=node.localName
			if tagName=="TypeAlias":
				global alias_types
				aliases = []
				handleTypeAlias(node,"",aliases)
				for alias in aliases:
					typeNameOutput = pyParseTypeName(alias[0],{})
					if len(typeNameOutput[1]) == 0:
						alias_types += "parse%s\t\t\t\t= %s;\n" % ( alias[1],typeNameOutput[0] )
					else:
						py_paramcontent = ""
						for paramname in typeNameOutput[1]:
							py_paramcontent += "," + paramname
						alias_types += "\n"
						alias_types += "function parse%s(parent,name,desc)\n" % ( alias[1] )
						alias_types += "\treturn %s(parent,name,desc%s);\n" % ( typeNameOutput[0],py_paramcontent )
						alias_types += "end\n"
						alias_types += "\n"
			elif tagName=="Struct":
				handleStruct(node,"")
				pass
			elif tagName=="Union":
				handleUnion(node,"")
				pass
			elif tagName=="Enum":
				global const_vars
				enums=[]
				handleEnum(node,enums)
				i=0
				data=[]
				for enum in enums:
					data.append([enum,"=%d;" % i])
					i +=1
				const_vars+=tabData(0,data)
				pass

def handleTypeAlias(node,p_name,aliases = None):
	sourceName = getText(getElement(node,"SourceType"))
	aliaName = getText(getElement(node,"Alias"))
	try:
		desc = getText(getElement(node,"Description"))
	except IndexError:
		desc = ""
	if p_name != "":
		return #不前不支持
	type_name = transferTypeName(sourceName)
	if aliases is not None:
		aliases.append( [type_name,aliaName] )

def handleEnum(node,enums=None):
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	try:
		desc = getText(getElement(node,"Description"))
	except IndexError:
		desc = ""
	items = getElements(node,"Item");
	for item in items:
		name = getText(getElement(item,"Name"))
		if enums is not None:
			enums.append(name)

files=glob.glob("%s/Proto_*.xml" % PATH_PROTO_SOURCE)
files.sort()
for file in files:
	dom = xml.dom.minidom.parse(file)
	handleProto(getElement(dom,"Proto"))

content=""

#生成错误号定义
data=[]
errs_items=ERRS.items()
for k,v in errs_items:
	data.append(["%s" % k,"=%d;" % v])
const_vars += tabData(0,data)

content+=const_vars
if const_vars != "":
	content += "\n"
content+=alias_types
if alias_types != "":
	content += "\n"
content+=parse_function
content+=trigger_function
content+="""
function main()
	InitSystemTriggers();
"""
content+=trigger_register
content+="end"

o_flag = os.O_WRONLY|os.O_CREAT|os.O_TRUNC
try:
	o_flag |= os.O_BINARY
except AttributeError:
	pass

filename = "%s/MessageParse/config/parse.lua" % PATH_TOOL_TARGET
os.write(os.open(filename,o_flag),content)

filename = "%s/Client/parse.lua" % PATH_PROTO_TARGET
os.write(os.open(filename,o_flag),content)
