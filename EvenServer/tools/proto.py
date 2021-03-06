#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-

import os
import re
import sys
import time
from utils import *
from config import *

if len(sys.argv)!=2:
	print "Usage:\n\t./proto.py <xmlfile>\n"
	sys.exit(0)

o_flag = os.O_WRONLY|os.O_CREAT|os.O_TRUNC
try:
	o_flag |= os.O_BINARY
except AttributeError:
	pass

FILE_NAME="%s/%s" % (PATH_PROTO_SOURCE,sys.argv[1])

def tryUpdateCommand(filename):
	xml_time   =   os.path.getmtime(filename)
	update_command = False
	try:
		x_time = os.path.getmtime( "%s/protoup.x" % PATH_PROTO_SOURCE)
		if x_time < xml_time:
			update_command = True
	except:
		update_command = True
	
	if update_command:
		execfile("%s/cmd_up.py" % PATH_TOOL_SOURCE)

#tryUpdateCommand(FILE_NAME)

#execfile("%s/cmd_def.py" % PATH_PROTO_SOURCE)

#输出文件名
OUTPUT_NAME=""
#输出文件内容
content={}
initHostDict(content,"")
#消息体
messages_body={}
initHostDict(messages_body,"")
#消息错误号
messages_error={}
initHostDict(messages_error,{})
#算法实现
implement={}
initHostDict(implement,"")
#自动特性实现
autofuncs={}
initHostDict(autofuncs,"")
#是否类型定义文件
types_xml = 0
#是否消息定义文件
message_xml = 0
#rana输入代码
rana_code={}
initHostDict(rana_code,"")

import xml.dom.minidom

#追加内容
def append(s,hosts=ALL_HOSTS):
	global content
	for host in hosts:
		content[host] += s
		content[host] +='\n'

#处理总节点(Proto节点)
def handleProto(proto):
	#目标文件名称
	name=getText(getElements(proto,"Name")[0])
	global OUTPUT_NAME
	global types_xml
	global append
	global handleInclude
	global handleTypes
	global handleMessage
	OUTPUT_NAME = "%s.h" % name
	if OUTPUT_NAME[-8:-2].upper() == "_TYPES":
		types_xml=1
	#头文件预定义
	head_define = "__%s_H" % name.upper()
	append("#ifndef %s" % head_define)
	append("#define %s" % head_define)
	append("")
	#文件注释
	append("/*")
	descs=getElements(getElement(proto,"Descriptions"),"Description")
	for desc in descs:
		append(getText(desc))
	append("*/")
	append("")
	#头文件包含
	includes=getElements(getElement(proto,"Headers"),"Include")
	for include in includes:
		handleInclude(include)
	append("")
	#协议相关类型定义
	handleTypes(getElement(proto,"Types"))
	append("")
	#自定义代码
	codes=getElements(getElement(proto,"Codes"),"Code")
	if len(codes) > 0:
		append("namespace Config")
		append("{//自定义代码")
		for code in codes:
			lines=getText(code).split("\n")
			for line in lines:
				append(tabStr(1,"%s",line))
		append("}")
		append("")
	#消息处理
	global messages_body
	global messages_error
	messages=getElements(getElement(proto,"Messages"),"Message")
	for message in messages:
		handleMessage(message)

	for host in ALL_HOSTS:
		if messages_body[host] == "" and ( len(messages_error[host].keys()) <= 0 ):
			continue
		append("namespace Config",[host])
		append("{//协议定义",[host])
		errors=messages_error[host].keys()
		if len(errors):
			append("\t//错误号声明",[host])
			for error in errors:
				append(tabStr(1,"extern const ErrorType %s;",error),[host])
			append("",[host])
		append(messages_body[host],[host])
		append("}",[host])
		append("",[host])
	#加入实现代码
	for host in ALL_HOSTS:
		if autofuncs[host] != "":
			append("namespace Config",[host])
			append("{//自动函数",[host])
			append(autofuncs[host]+"}\n",[host])
	for host in ALL_HOSTS:
		if implement[host] != "":
			append("namespace Config",[host])
			append("{//封包函数",[host])
			append(implement[host]+"}\n",[host])

	#加入rana代码
	global rana_code
	for host in ALL_HOSTS:
		if rana_code[host]!="":
			append("#ifdef __RANAINPUTSTACK_H",[host])
			append("namespace",[host])
			append("{//rana代码",[host])
			append(rana_code[host]+"}",[host])
			append("#endif",[host])
			append("",[host])
	#最后的#endif
	global content
	append("#endif")

def handleTypes(types):
	global handleStruct
	global handleUnion
	global handleEnum
	global handleEnumImport
	append("namespace Config")
	append("{//协议相关类型定义")
	for node in types.childNodes:
		if node.hasChildNodes():
			tagName=node.localName
			if tagName=="Code":
				lines=getText(node).split("\n")
				for line in lines:
					append(tabStr(1,"%s",line))
				pass
			elif tagName=="TypeAlias":
				append(handleTypeAlias(ALL_HOSTS,1,node,""))
				pass
			elif tagName=="Struct":
				append(handleStruct(ALL_HOSTS,1,node,"")+";")
				pass
			elif tagName=="Union":
				#append(handleUnion(ALL_HOSTS,1,node,"")+";")
				pass
			elif tagName=="Enum":
				append(handleEnum(1,node)+";")
				pass
			elif tagName=="EnumImport":
				append(handleEnumImport(1,node)+";")
				pass


	append("}")
	
def handleTypeAlias(hosts,tabnum,node,prefix):
	sourceName = getText(getElement(node,"SourceType"))
	aliaName = getText(getElement(node,"Alias"))
	try:
		descs = getText(getElement(node,"Description")).split("\n")
	except IndexError:
		descs = [""]
	res=tabStr(tabnum,"typedef\t\t%s\t\t%s;",sourceName,aliaName)
	if descs[0]!="":
		res += "\t//%s" % descs[0]

	descs_len=len(descs)
	if descs_len > 1:
		res += "\n"
		i = 1
		res += tabStr(tabnum,"/*")
		while i < descs_len:
			res += tabStr(tabnum+1,"%s",descs[i])
			i += 1
		res += tabStr(tabnum,"*/")

	return res

def handleStruct(hosts,tabnum,node,prefix,parentSucceeds=None):
	#struct被认为独立结构,每个struct独立解析
	succeeds = createEmptySucceedAttrib()
	if parentSucceeds != None:
		for succeedKey,hasFunction in parentSucceeds.items():
			succeeds[succeedKey] = hasFunction
	if succeeds["compare_less"] or succeeds["compare_greater"]:
		succeeds["compare_equal"]=True
		succeeds["compare_unequal"]=True
	try:
		if getText(getElement( getElement(node,"Rana"),"input"))=="true":
			succeeds["rana_in"]=True
	except IndexError:
		pass
	try:
		if getText(getElement( getElement(node,"Rana"),"output"))=="true":
			succeeds["rana_out"]=True
	except IndexError:
		pass
	try:
		if getText(getElement( getElement(node,"AutoCompare"),"less"))=="true":
			succeeds["compare_less"]=True
	except IndexError:
		pass
	try:
		if getText(getElement( getElement(node,"AutoCompare"),"greater"))=="true":
			succeeds["compare_greater"]=True
	except IndexError:
		pass
	try:
		if getText(getElement( getElement(node,"AutoCompare"),"equal"))=="true":
			succeeds["compare_equal"]=True
	except IndexError:
		pass
	try:
		if getText(getElement( getElement(node,"AutoCompare"),"unequal"))=="true":
			succeeds["compare_unequal"]=True
	except IndexError:
		pass
	
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	try:
		desc = getText(getElement(node,"Description"))
	except IndexError:
		desc = ""
	res=tabStr(tabnum,"struct %s",name)
	if desc!="":
		res += "\t//%s" % desc
	res += "\n"

	res += handleIsolatedStructMembers(hosts,tabnum,node,prefix,name,succeeds)
	return res

def handleUnion(hosts,tabnum,node,prefix,names=None,succeeds=None):
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	try:
		desc = getText(getElement(node,"Description"))
	except IndexError:
		desc = ""
	try:
		codes = getText(getElement(node,"Code")).split("\n")
	except IndexError:
		codes = []
	res=tabStr(tabnum,"union %s",name)
	if desc!="":
		res += "\t//%s" % desc
	res += "\n"

	if names==None:
		names = createEmptyNameList()

	names["self"] = name

	res += tabStr(tabnum,"{\n")

	res += handleMembers(hosts,tabnum,node,prefix+name+"::",names,succeeds)

	res+=tabStr(tabnum,"}")

	return res

def handleEnum(tabnum,node,enums=None):
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	try:
		desc = getText(getElement(node,"Description"))
	except IndexError:
		desc = ""
	items = getElements(node,"Item");
	res=tabStr(tabnum,"enum %s",name)
	if desc!="":
		res += "\t//%s" % desc
	res += "\n"
	res += tabStr(tabnum,"{\n")
	data = []
	for item in items:
		name = getText(getElement(item,"Name"))
		if enums is not None:
			enums.append(name)
		try:
			value = getText(getElement(item,"Value"))
			enumcode = "%s = %s," % (name, value)
		except IndexError:
			enumcode = "%s," % name
		try:
			desc = getText(getElement(item,"Description"))
		except IndexError:
			desc = ""
		if desc!="":
			desc = "//%s" % desc
		data.append([enumcode,desc])
	res += tabData(tabnum+1,data)
	res += tabStr(tabnum,"}")
	return res	

def handleEnumImport(tabnum,node,enums=None):
	fileName = getText(getElement(node,"File"))
	enumName = getText(getElement(node,"EnumName"))
	dom = xml.dom.minidom.parse("%s/%s" % (PATH_PROTO_SOURCE, fileName))
	protoNode = getElement(dom,"Proto")
	typesNode = getElement(protoNode, "Types")
	enumNodes = getElements(typesNode, "Enum")
	MatchedEnumNode = None
	for enumNode in enumNodes:
		name = getText(getElement(enumNode,"Name"))
		if name == enumName:
			MatchedEnumNode = enumNode
			break
	if MatchedEnumNode <> None:
		return handleEnum(tabnum, MatchedEnumNode, enums)
	else:
		print "Cannot find importing enum : %s in %s" % (enumName, fileName)
		return None
		
def handleInclude(include):
	append("#include <%s>" % getText(include))

#生成rana代码
def ranaGet(tabnum,name):
	dot_pos=name.find(".")
	if dot_pos!=-1:
		parent=name[0:dot_pos]
		sub=name[dot_pos+1:]
		result = tabStr(tabnum,"try\n");
		result += tabStr(tabnum,"{\n");
		result += tabStr(tabnum+1,"RanaSubTable sub(L,index,\"%s\");\n",parent);
		result += tabStr(tabnum+1,"rana_get(L,sub.index,\"%s\",p.%s);\n",sub,name);
		result += tabStr(tabnum,"}catch(RanaInputArgumentException *e)\n");
		result += tabStr(tabnum,"{\n");
		result += tabStr(tabnum+1,"e->appendPrefix(\"%s\");\n",parent);
		result += tabStr(tabnum+1,"throw e;\n");
		result += tabStr(tabnum,"}\n");
		return result;
	else:
		return tabStr(tabnum,"rana_get(L,index,\"%s\",p.%s);\n",name,name)

def ranaPush(tabnum,name):
	dot_pos=name.find(".")
	if dot_pos!=-1:
		return "//\n";
	else:
		result = tabStr(tabnum,"rana_push(L,\"%s\");\n",name)
		result += tabStr(tabnum,"rana_push(L,p.%s);\n",name)
		result += tabStr(tabnum,"lua_settable(L,-3);\n\n")
		return result
		

def appendSwitch(codes,switch):
	if len(switch) > 0:
		if len(switch[1]) > 1:
			codes.append([1,switch[0],switch[1]])
		else:
			codes.append([0,switch[0]+"=="+switch[1][0][0],switch[1][0][1]])
		del switch[:]


def createEmptyNameList():
	names={}
	#names名称列表,其中
	#enums直接的枚举
	#self:自己的名称;
	#types:自己内部被申明的内联结构,内容和自己相同,目前只有Union;
	#variables:自己的直属成员变量,按照声明顺序
	names["self"] = ""
	names["enums"]=[]
	names["types"] = {}
	names["variables"] = []
	#variables变量列表,每个元素为一个字典其中:
	#	"type"代表自己的类型
	#	"name"为自己的名称
	#	"conds"代表自己的条件
	#	"copies"代表自己的自动拷贝规则,数组,每个元素为一个字典:
	#			"name":来源的结构(类)名称
	#			"valueName":来源变量内容
	#			"valuePrefix":来源变量前缀(""全局;"o."目标结构内部;"p."本结构内部)
	return names

def createEmptySucceedAttrib():
	succeeds = {}
	#succeeds继承信息列表,其中
	#Rana功能
	succeeds["rana_in"] = False							#是否支持自动Rana输入
	succeeds["rana_out"] = False						#是否支持自动Rana输出
	#自动比较功能
	succeeds["compare_less"] = False				#是否支持对自身的小于(<)操作符
	succeeds["compare_greater"] = False			#是否支持对自身的大于(>)操作符
	succeeds["compare_equal"] = False				#是否支持对自身的等于(==)操作符
	succeeds["compare_unequal"] = False			#是否支持对自身的不等于(!=)操作符
	return succeeds

def parseNameList(names,globalPrefix,prefix="",trunkNames=[],enumsForTrunk={}):
	global getSubItemsFromTypeName
	global adjustCondition
	global isEqualCondition
	global appendSwitch

	for variableItem in names["variables"]:
		if getSubItemsFromTypeName(names,variableItem["type"]) == None:
			trunkNames.append(prefix+variableItem["name"])
	
	#变更枚举映射
	for enum in names["enums"]:
		enumsForTrunk[enum] = globalPrefix+prefix+names["self"]+"::"

	output = {}
	output["copies"] = {}
	output["needCopyCount"] = 0
	output["conditions"] = [] #[0,条件,[原始信息,额外前缀],原始条件] 或 [1,switch变量,[[ 值,[名称] ],原始条件]]
	output["types"] = {}
	for typename,subnames in names["types"].items():
		output["types"][typename] = parseNameList(subnames,globalPrefix,prefix+names["self"]+"::",trunkNames,enumsForTrunk)

	#重置枚举映射(因为内联类里面可能会有同名枚举)
	for enum in names["enums"]:
		enumsForTrunk[enum] = prefix+names["self"]+"::"

	#将相邻的相同条件合并在一起
	name_conds=[]	#[条件,[名称,...]]
	names_len = len(names["variables"])
	if names_len >0:
		name_cond= []
		name_cond.append( names["variables"][0]["conds"] )
		name_cond.append([ [names["variables"][0],""] ])
		cur_cond= names["variables"][0]["conds"] 
		i=1
		while i < names_len:
			if names["variables"][i]["conds"]==cur_cond:
				name_cond[1].append( [names["variables"][i],""] )
			else:
				name_conds.append(name_cond)
				name_cond = []
				name_cond.append( names["variables"][i]["conds"] )
				name_cond.append([ [names["variables"][i],""] ])
				cur_cond=names["variables"][i]["conds"]
			i += 1
		name_conds.append(name_cond)

	#将变量名称与值设为合适的值
	for name_cond in name_conds:
		for enum,enumPrefix in enumsForTrunk.items():
			name_cond[0]=name_cond[0].replace(enum,enumPrefix+enum)
		name_cond[0]=adjustCondition(trunkNames,name_cond[0])

	#switch语句判断,生成最终的代码内部表示
	switch=[]	# [switch变量,[[ 值,[原始信息,额外前缀],原始条件 ]] ]
	for name_cond in name_conds:
		if isEqualCondition(name_cond[0]):	#如果是相等条件
			name_value=name_cond[0].split("==")
			if len(switch)>0:
				if name_value[0]==switch[0]:	#新的值
					switch[1].append([name_value[1],name_cond[1]])
				else:
					appendSwitch(output["conditions"],switch)
					switch.append(name_value[0])
					switch.append([[ name_value[1],name_cond[1]]])
			else:
				switch.append(name_value[0])
				switch.append([[ name_value[1],name_cond[1]] ])
		else:
			appendSwitch(output["conditions"],switch)
			output["conditions"].append([0,name_cond[0],name_cond[1]])
	appendSwitch(output["conditions"],switch)

	#自动拷贝所需类分析
	#		继承自类的自动拷贝
	for typename,outinfo in output["types"].items():
		output["needCopyCount"] += outinfo["needCopyCount"]
		for copy_class,resultItem in outinfo["copies"].items():
			if not( copy_class in output["copies"]):
				output["copies"][copy_class] = 0
			output["copies"][copy_class] += resultItem
	#		分析自身的自动拷贝
	for value in names["variables"]:
		if getSubItemsFromTypeName(names,value["type"]) != None:
			continue	#忽略内联变量
		output["needCopyCount"] += 1
		for copy_type in value["copies"]:
			copy_class = copy_type["name"]
			if not( copy_class in output["copies"] ):
				output["copies"][copy_class] = 0
			output["copies"][copy_class] += 1
	return output

def handleIsolatedStructMembers(hosts,tabnum,node,prefix,typename,succeeds=None):
	global createEmptyNameList
	global createEmptySucceedAttrib
	global handleMembers
	global parseNameList
	res = tabStr(tabnum,"{\n")

	names = createEmptyNameList()
	names["self"] = typename

	if succeeds is None:
		succeeds=createEmptySucceedAttrib()	#自动类间拷贝字典

	res += handleMembers(hosts,tabnum,node,prefix+typename+"::",names,succeeds)
	
	parseInfo = parseNameList(names,prefix)
	
	if succeeds["compare_less"]:
		res += tabStr(tabnum+1,"bool operator < ( const %s & o ) const;\n",typename)
	if succeeds["compare_greater"]:
		res += tabStr(tabnum+1,"bool operator > ( const %s & o ) const;\n",typename)
	if succeeds["compare_equal"]:
		res += tabStr(tabnum+1,"bool operator == ( const %s & o ) const;\n",typename)
	if succeeds["compare_unequal"]:
		res += tabStr(tabnum+1,"bool operator != ( const %s & o ) const;\n",typename)
	
	for copy_class,copy_items in parseInfo["copies"].items():
		extraDesc = ""
		if parseInfo["needCopyCount"] > copy_items:
			extraDesc = "//Warning: Not all variables is copied in this copy rule!!(%d/%d)" %(copy_items,parseInfo["needCopyCount"])
		elif parseInfo["needCopyCount"] != copy_items:
			extraDesc = "//Warning: Need Copy Count(%d) Less Than Copied Items(%d)!!" % (parseInfo["needCopyCount"],copy_items)
		res += tabStr(tabnum+1,"%s & operator = ( const %s & o );%s\n",typename,copy_class,extraDesc)

	res+=tabStr(tabnum,"}")

	#自动生成msgcode判断
	#code_i 输入代码 code_o 输出代码
	global implement
	code_i = tabStr(1,"inline Zoic::Message & operator << ( Zoic::Message &m,const %s & p )\n",prefix+typename)
	code_o = tabStr(1,"inline Zoic::Message & operator >> ( Zoic::Message &m,%s & p )\n",prefix+typename)
	code_i += tabStr(1,"{\n")
	code_o += tabStr(1,"{\n")

	global createMsgInputCode
	global createMsgOutputCode
	code_i += createMsgInputCode(2,parseInfo)
	code_o += createMsgOutputCode(2,parseInfo)

	code_i += tabStr(2,"return m;\n")
	code_o += tabStr(2,"return m;\n")
	code_i += tabStr(1,"}\n\n")
	code_o += tabStr(1,"}\n\n")

	for host in hosts:
		implement[host] += code_i
		implement[host] += code_o

	#自动生成Rana输入输出代码
	global rana_code
	#rana_i 输入代码,对应0 rana_o 输出代码,对应1
	if succeeds["rana_in"]:
		rana_i = tabStr(1,"inline void rana_push(RanaState L,const Proto::%s & p)\n",prefix+typename)
		rana_i += tabStr(1,"{\n")
		rana_i += tabStr(2,"using namespace Config;\n")
		
		global createRanaInputCode
		rana_i += createRanaInputCode(2,parseInfo)

		rana_i += tabStr(1,"}\n\n")
			
	if succeeds["rana_out"]:
		rana_o = tabStr(1,"inline void rana_get(RanaState L,int index,Proto::%s & p)\n",prefix+typename)
		rana_o += tabStr(1,"{\n")
		rana_o += tabStr(2,"using namespace Config;\n")

		global createRanaOutputCode
		rana_o += createRanaOutputCode(2,parseInfo)

		rana_o += tabStr(1,"}\n\n")

	for host in hosts:
		if succeeds["rana_in"]:
			rana_code[host] += rana_i
		if succeeds["rana_out"]:
			rana_code[host] += rana_o
	
	#自动生成比较代码
	global autofuncs
	comp_code = ""
	if succeeds["compare_less"]:
		comp_code += tabStr(1,"inline bool %s::operator <( const %s & o ) const\n",prefix+typename,prefix+typename)
		comp_code += tabStr(1,"{\n")
		comp_code += tabStr(2,"const %s & p = *this;\n",typename)
		global createAutoLessCode
		comp_code += createAutoLessCode(2,parseInfo)
		comp_code += tabStr(2,"return false;\n")
		comp_code += tabStr(1,"}\n\n")
	if succeeds["compare_greater"]:
		comp_code += tabStr(1,"inline bool %s::operator >( const %s & o ) const\n",prefix+typename,prefix+typename)
		comp_code += tabStr(1,"{\n")
		comp_code += tabStr(2,"const %s & p = *this;\n",typename)
		global createAutoGreaterCode
		comp_code += createAutoGreaterCode(2,parseInfo)
		comp_code += tabStr(2,"return false;\n")
		comp_code += tabStr(1,"}\n\n")
	if succeeds["compare_equal"]:
		comp_code += tabStr(1,"inline bool %s::operator ==( const %s & o ) const\n",prefix+typename,prefix+typename)
		comp_code += tabStr(1,"{\n")
		comp_code += tabStr(2,"const %s & p = *this;\n",typename)
		global createAutoEqualCode
		comp_code += createAutoEqualCode(2,parseInfo)
		comp_code += tabStr(2,"return true;\n")
		comp_code += tabStr(1,"}\n\n")
	if succeeds["compare_unequal"]:
		comp_code += tabStr(1,"inline bool %s::operator !=( const %s & o ) const\n",prefix+typename,prefix+typename)
		comp_code += tabStr(1,"{\n")
		comp_code += tabStr(2,"return !(*this == o);\n")
		comp_code += tabStr(1,"}\n\n")

	for host in hosts:
		autofuncs[host] += comp_code


	#自动生成拷贝代码
	for copy_class,copy_items in parseInfo["copies"].items():
		code_func = tabStr(1,"inline %s & %s::operator =( const %s & o )\n",prefix+typename,prefix+typename,copy_class)
		code_func += tabStr(1,"{\n")
		code_func += tabStr(2,"%s & p = *this;\n",typename)
	
		global createAutoCopyCode
		code_func += createAutoCopyCode(2,parseInfo,copy_class)
		
		code_func += tabStr(2,"return p;\n")
		code_func += tabStr(1,"}\n\n")
		for host in hosts:
			autofuncs[host] += code_func

	return res

def getSubItemsFromTypeName(items,typename):
	name = ""
	currentItems = items
	tail = typename
	ipos = tail.find("::")
	while ipos > 0:
		head = tail[0:ipos]
		tail = tail[ipos+2:]
		if not ( head in currentItems["types"] ):
			return None
		currentItems = currentItems["types"][head]
		ipos = tail.find("::")
	if not ( tail in currentItems["types"] ):
		return None
	return currentItems["types"][tail]

def createMsgInputCode(tabnum,parseInfo,nameprefix=""):
	ret_code = ""
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createMsgInputCode(tabnum+2,subParseInfo,nameprefix+valueitem[0]["name"]+".")
					else:
						ret_code += tabStr(tabnum+2,"m << p.%s;\n",nameprefix+valueitem[0]["name"])
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createMsgInputCode(tabnum+nametab,subParseInfo,nameprefix+valueitem[0]["name"]+".")
				else:
					ret_code += tabStr(tabnum+nametab,"m << p.%s;\n",nameprefix+valueitem[0]["name"])
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	return ret_code

def createMsgOutputCode(tabnum,parseInfo,nameprefix=""):
	ret_code = ""
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createMsgOutputCode(tabnum+2,subParseInfo,nameprefix+valueitem[0]["name"]+".")
					else:
						ret_code += tabStr(tabnum+2,"m >> p.%s;\n",nameprefix+valueitem[0]["name"])
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createMsgOutputCode(tabnum+nametab,subParseInfo,nameprefix+valueitem[0]["name"]+".")
				else:
					ret_code += tabStr(tabnum+nametab,"m >> p.%s;\n",nameprefix+valueitem[0]["name"])
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	return ret_code

def createRanaInputCode(tabnum,parseInfo,nameprefix=""):
	ret_code = ""
	ret_code += tabStr(tabnum,"lua_newtable(L);\n")
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					ret_code += tabStr(tabnum+2,"rana_push(L,\"%s\");\n",valueitem[0]["name"])
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createRanaInputCode(tabnum+2,subParseInfo,nameprefix+valueitem[0]["name"]+".")
					else:
						ret_code += tabStr(tabnum+2,"rana_push(L,p.%s);\n",nameprefix+valueitem[0]["name"])
					ret_code += tabStr(tabnum+2,"lua_settable(L,-3);\t//push \"%s\"\n",nameprefix+valueitem[0]["name"])
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				ret_code += tabStr(tabnum+nametab,"rana_push(L,\"%s\");\n",valueitem[0]["name"])
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createRanaInputCode(tabnum+nametab,subParseInfo,nameprefix+valueitem[0]["name"]+".")
				else:
					ret_code += tabStr(tabnum+nametab,"rana_push(L,p.%s);\n",nameprefix+valueitem[0]["name"])
				ret_code += tabStr(tabnum+nametab,"lua_settable(L,-3);\t//push \"%s\"\n",nameprefix+valueitem[0]["name"])
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	return ret_code

def createRanaOutputCode(orgTabNum,parseInfo,nameprefix=""):
	ret_code = ""
	tabnum = orgTabNum
	indexName = "index"
	if nameprefix!="":
		parent=nameprefix[0:len(nameprefix)-1 ]
		ret_code = tabStr(tabnum,"try\n");
		ret_code += tabStr(tabnum,"{\n");
		tabnum += 1
		ret_code += tabStr(tabnum,"RanaSubTable sub(L,index,\"%s\");\n",parent);
		indexName = "sub.index"
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createRanaOutputCode(tabnum+2,subParseInfo,nameprefix+valueitem[0]["name"]+".")
					else:
						ret_code += tabStr(tabnum+2,"rana_get(L,%s,\"%s\",p.%s);\n",indexName,nameprefix+valueitem[0]["name"],nameprefix+valueitem[0]["name"])
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createRanaOutputCode(tabnum+nametab,subParseInfo,nameprefix+valueitem[0]["name"]+".")
				else:
					ret_code += tabStr(tabnum+nametab,"rana_get(L,%s,\"%s\",p.%s);\n",indexName,nameprefix+valueitem[0]["name"],nameprefix+valueitem[0]["name"])
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	if nameprefix!="":
		tabnum -= 1
		ret_code += tabStr(tabnum,"}catch(RanaInputArgumentException *e)\n");
		ret_code += tabStr(tabnum,"{\n");
		ret_code += tabStr(tabnum+1,"e->appendPrefix(\"%s\");\n",parent);
		ret_code += tabStr(tabnum+1,"throw e;\n");
		ret_code += tabStr(tabnum,"}\n");
	return ret_code
		
def createAutoCopyCode(tabnum,parseInfo,copyName,nameprefix=""):
	ret_code = ""
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createAutoCopyCode(tabnum+2,subParseInfo,copyName,nameprefix+valueitem[0]["name"]+".")
					else:
						copyInfo = None
						for copy_type in valueitem[0]["copies"]:
							if copyName == copy_type["name"]:
								copyInfo = copy_type
						if copyInfo == None:
							continue
						objectName = copyInfo["valueName"]
						if objectName == "" and copyInfo["valuePrefix"] == "o.":
							objectName = nameprefix+valueitem[0]["name"]
						ret_code += tabStr(tabnum+2,"p.%s = %s%s;\n",nameprefix+valueitem[0]["name"],copyInfo["valuePrefix"],objectName)
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createAutoCopyCode(tabnum+nametab,subParseInfo,copyName,nameprefix+valueitem[0]["name"]+".")
				else:
					copyInfo = None
					for copy_type in valueitem[0]["copies"]:
						if copyName == copy_type["name"]:
							copyInfo = copy_type
					if copyInfo == None:
						continue
					objectName = copyInfo["valueName"]
					if objectName == "" and copyInfo["valuePrefix"] == "o.":
						objectName = valueitem[0]["name"]
					ret_code += tabStr(tabnum+nametab,"p.%s = %s%s;\n",nameprefix+valueitem[0]["name"],copyInfo["valuePrefix"],objectName)
			if have_if:
				ret_code += tabStr(2,"}\n")
	return ret_code

def createAutoLessCode(tabnum,parseInfo,nameprefix=""):
	ret_code = ""
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					currentName = nameprefix+valueitem[0]["name"]
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createAutoLessCode(tabnum+2,subParseInfo,currentName+".")
					else:
						ret_code += tabStr(tabnum+2,"if(%s != o.%s)\n",currentName,currentName)
						ret_code += tabStr(tabnum+2,"{\n")
						ret_code += tabStr(tabnum+3,"return %s < o.%s;\n",currentName,currentName)
						ret_code += tabStr(tabnum+2,"}\n")
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				currentName = nameprefix+valueitem[0]["name"]
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createAutoLessCode(tabnum+nametab,subParseInfo,currentName+".")
				else:
					ret_code += tabStr(tabnum+nametab,"if(%s != o.%s)\n",currentName,currentName)
					ret_code += tabStr(tabnum+nametab,"{\n")
					ret_code += tabStr(tabnum+nametab+1,"return %s < o.%s;\n",currentName,currentName)
					ret_code += tabStr(tabnum+nametab,"}\n")
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	return ret_code

def createAutoGreaterCode(tabnum,parseInfo,nameprefix=""):
	ret_code = ""
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					currentName = nameprefix+valueitem[0]["name"]
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createAutoGreaterCode(tabnum+2,subParseInfo,currentName+".")
					else:
						ret_code += tabStr(tabnum+2,"if(%s != o.%s)\n",currentName,currentName)
						ret_code += tabStr(tabnum+2,"{\n")
						ret_code += tabStr(tabnum+3,"return %s > o.%s;\n",currentName,currentName)
						ret_code += tabStr(tabnum+2,"}\n")
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				currentName = nameprefix+valueitem[0]["name"]
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createAutoGreaterCode(tabnum+nametab,subParseInfo,currentName+".")
				else:
					ret_code += tabStr(tabnum+nametab,"if(%s != o.%s)\n",currentName,currentName)
					ret_code += tabStr(tabnum+nametab,"{\n")
					ret_code += tabStr(tabnum+nametab+1,"return %s > o.%s;\n",currentName,currentName)
					ret_code += tabStr(tabnum+nametab,"}\n")
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	return ret_code

def createAutoEqualCode(tabnum,parseInfo,nameprefix=""):
	ret_code = ""
	for code in parseInfo["conditions"]:
		if code[0]==1:	#switch代码
			ret_code += tabStr(tabnum,"switch(%s)\n",code[1])
			ret_code += tabStr(tabnum,"{\n")
			for value in code[2]:
				ret_code += tabStr(tabnum+1,"case %s:\n",value[0])
				for valueitem in value[1]:
					currentName = nameprefix+valueitem[0]["name"]
					subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
					if subParseInfo != None:
						ret_code += createAutoEqualCode(tabnum+2,subParseInfo,currentName+".")
					else:
						ret_code += tabStr(tabnum+2,"if(%s != o.%s)\n",currentName,currentName)
						ret_code += tabStr(tabnum+2,"{\n")
						ret_code += tabStr(tabnum+3,"return false;\n")
						ret_code += tabStr(tabnum+2,"}\n")
				ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum+1,"default:\n")
			ret_code += tabStr(tabnum+2,"break;\n")
			ret_code += tabStr(tabnum,"}\n")
		else:	#if代码
			if code[1]!="":
				have_if=1
				nametab=1
			else:
				have_if=0
				nametab=0
			if have_if:
				ret_code += tabStr(tabnum,"if(%s)\n",code[1])
				ret_code += tabStr(tabnum,"{\n");
			for valueitem in code[2]:
				currentName = nameprefix+valueitem[0]["name"]
				subParseInfo = getSubItemsFromTypeName( parseInfo,valueitem[0]["type"] )
				if subParseInfo != None:
					ret_code += createAutoEqualCode(tabnum+nametab,subParseInfo,currentName+".")
				else:
					ret_code += tabStr(tabnum+nametab,"if(%s != o.%s)\n",currentName,currentName)
					ret_code += tabStr(tabnum+nametab,"{\n")
					ret_code += tabStr(tabnum+nametab+1,"return false;\n")
					ret_code += tabStr(tabnum+nametab,"}\n")
			if have_if:
				ret_code += tabStr(tabnum,"}\n")
	return ret_code


#处理结构或联合内成员列表
def handleMembers(hosts,tabnum,node,prefix,names,succeeds=None):
	global handleMember

	members=getElements(node,"Member")

	data = []	#成员内容 type name desc
	for member in members:
		handleMember(hosts,tabnum+1,member,data,names,prefix,succeeds)
	res = tabData(tabnum+1,data)
	#自定义代码
	try:
		codes = getText(getElement(node,"Code")).split("\n")
	except IndexError:
		codes = []
	for code in codes:
		res += tabStr(tabnum+1,"%s\n",code)
	
	return res

#调整单词
def adjustWord(variableNames,word):
	result = word
	for variable in variableNames:
		if word==variable:
			result="p."+word
			break
	return result

#调整条件
def adjustCondition(variableNames,condition):
	global adjustWord
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
				result+=adjustWord(variableNames,word)
			result+=ch
			word=""
		index +=1
	if word!="":
		result+=adjustWord(variableNames,word)
	return result

#是否相等的条件
def isEqualCondition(condition):
	if condition.find("&&")!=-1:
		return 0
	if condition.find("||")!=-1:
		return 0
	return condition.find("==")!=-1

#处理结构或联合内单个成员
def handleMember(hosts,tabnum,node,data,names,prefix,succeeds=None):
	#类型定义
	typenode=node.firstChild
	while not typenode.hasChildNodes():
		typenode=typenode.nextSibling
	tagName=typenode.localName
	hasNewDefine = False
	type_name = ""
	if tagName=="Type":
		type_name=getText(typenode)
	else:
		try:
			type_name = getText(getElement(typenode,"Name"))
		except IndexError:
			pass
		hasNewDefine = True
		if tagName=="Struct":
			res=handleStruct(hosts,tabnum,typenode,prefix,succeeds)
		elif tagName=="Union":
			names["types"][type_name]= createEmptyNameList()	#联合内的成员名称定义
			res=handleUnion(hosts,tabnum,typenode,prefix,names["types"][type_name],succeeds)
		elif tagName=="Enum":
			res=handleEnum(tabnum,typenode,names["enums"])
		else:
			print res
	if type_name == "":
		type_name = "__UnknowType_%s__" % tagName
	try:
		name = getText(getElement(node,"Name"))
	except IndexError:
		name = ""
	try:
		descs = getText(getElement(node,"Description")).split("\n")
	except IndexError:
		descs = [""]
	try:
		condition = getText(getElement(node,"Condition"))
	except IndexError:
		condition = ""
	try:
		autoCopies = getElements( getElement(node,"AutoCopy"),"CopyRule" )
	except IndexError:
		autoCopies = []

	copies = []
	for copy_type in autoCopies:
		copyInfo = {}
		copyInfo["name"] = getText(getElement(copy_type,"TypeName"))
		copyInfo["valueName"] = ""
		copyInfo["valuePrefix"] = "o."
		try:
			copyInfo["valueName"] = getText(getElement(copy_type,"SourceValue"))
			try:
				scopeType = getText(getElement(copy_type,"ValueScope"))
				if scopeType == "global":
					copyInfo["valuePrefix"] = ""
				elif scopeType == "self":
					copyInfo["valuePrefix"] = "p."
			except IndexError:
				pass
		except IndexError:
			pass
		copies.append(copyInfo)

	if name!="":
		variableInfo = {}
		variableInfo["type"] = type_name
		variableInfo["name"] = name
		variableInfo["conds"] = condition
		variableInfo["copies"] = copies
		names["variables"].append(variableInfo)

	#说明
	if descs[0]!="" or condition!="":
		desc ="//"
		desc +=descs[0]
		if condition!="":
			if descs[0]!="":
				desc += " "
			desc += "("
			desc += condition
			desc += ")"
		if len(copies)!=0:
			desc += " [Import("
			copyCount = 0;
			for copyInfo in copies:
				if copyCount > 0:
					desc += ","
				desc += copyInfo["name"] + "::"
				if copyInfo["valueName"] == "" and copyInfo["valuePrefix"] == "o.":
					desc += name
				else:
					desc += copyInfo["valueName"]
				copyCount += 1
			desc += ")]"
	else:
		desc = ""

	#如果名称为空,则一定是定义了新的数据结构
	if name=="":
		data.append(res+";")
	else:
		if hasNewDefine==True:	#定义了新的数据结构，且定义了新的成员变量
			data.append(res[0:res.rfind("\n")])
			data.append(["}",name+";",desc])
		else:
			data.append([type_name,name+";",desc])
	#其它注释
	global messages_error
	descs_len=len(descs)
	if descs_len > 1:
		i = 1
		data.append(tabStr(tabnum,"/*"))
		while i < descs_len:
			if re.match("^ERROR_[A-Z_0-9]+$",descs[i]):
				for host in hosts:
					(messages_error[host])[descs[i]]=0
			data.append(tabStr(tabnum+1,"%s",descs[i]))
			i += 1
		data.append(tabStr(tabnum,"*/"))

def handleMessage(message):
	global messages_body
	global handleIsolatedStructMembers
	message_body=""
	descs=getText(getElement(message,"Description")).split("\n")
	name=getText(getElement(message,"Name"))
	type=getText(getElement(message,"Type"))
	fr_hosts=getText(getElement(message,"From")).replace("\n",",")
	to_hosts=getText(getElement(message,"To")).replace("\n",",")
	hosts_info=getHostLink(fr_hosts,to_hosts)
	fr=hosts_info[0]
	to=hosts_info[1]
	hosts=hosts_info[2]

	#注释
	message_body+=tabStr(1,"//%s %s->%s\n",descs[0],fr_hosts,to_hosts)
	descs_len=len(descs)
	if descs_len > 1:
		i = 1
		message_body+=tabStr(1,"/*\n")
		while i < descs_len:
			message_body+=tabStr(2,"%s\n",descs[i])
			i += 1
		message_body+=tabStr(1,"*/\n")
	cmd = HOST_TYPE[fr] + SEPARATOR_HOST + HOST_TYPE[to] + SEPARATOR_PROTO + name.upper() + SEPARATOR_ACTION + ACTION_TYPE[type].upper()
	global CMDS
	#命令声明
	try:
		message_body+=tabStr(1,"static const WORD %s=%d;\n",cmd,CMDS[cmd])
	except KeyError:
		print "Can't find %s" % cmd
		raise
	#结构定义
	p_name = "P" + SEPARATOR_PACKET + HOST_TYPE[fr] + SEPARATOR_HOST + HOST_TYPE[to] + SEPARATOR_PROTO + name + SEPARATOR_ACTION + ACTION_TYPE[type]
	message_body+=tabStr(1,"struct %s\n",p_name);
	message_body+=handleIsolatedStructMembers(hosts,1,getElement(message,"Content"),"",p_name)
	message_body+=";\n\n"
	for host in hosts:
		message_xml = 1
		messages_body[host] += message_body

dom = xml.dom.minidom.parse(FILE_NAME)
handleProto(getElement(dom,"Proto"))
if types_xml==0 or message_xml == 1:
	for host in ALL_HOSTS:
		if messages_body[host]!="":
			filename= "%s/%s/%s" % (PATH_PROTO_TARGET,host,OUTPUT_NAME)
			if needUpdateFile(filename,content[host]):
				os.write(os.open(filename,o_flag),content[host])
else:
	#filename= "%s/%s" % (PATH_PROTO_TARGET,OUTPUT_NAME)
	#if needUpdateFile(filename,content["None"]):
	#	os.write(os.open(filename,o_flag),content["None"])
	filename= "%s/%s" % (PATH_PROTO_TARGET,OUTPUT_NAME)
	if needUpdateFile(filename,content["None"]):
		os.write(os.open(filename,o_flag),content["None"])

#filename= "%s/%s" % (PATH_PROTO_SOURCE,OUTPUT_NAME.replace(".h",".x"))
#os.write(os.open(filename,o_flag),"")
