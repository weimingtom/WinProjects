#!/usr/local/bin/python
# -*- coding: iso-8859-1 -*-
import os

#主机定义
HOST_TYPE= \
{
	"RanaClient"		:"T",
	"RanaService"			:"S",
}
#主机关链定义
HOST_LINK= \
{
	"RanaClient"		:["Client"],
	"RanaService"			:["rana"],
}
#主机活跃性分类(不活跃的主机与其相关协议号优先保留，仅用于在发生打乱协议操作后绝对不应发生与更新操作事件相关的主机)
HOST_ACTIVITY= \
{
	"RanaClient"					:False,
	"RanaService"				:False,
}

