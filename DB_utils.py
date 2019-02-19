#encoding:utf-8
import pymysql,pymssql
import cx_Oracle
import redis
import psycopg2
from DBUtils.PooledDB import PooledDB
#Mysql数据库连接池
class OPMysql(object):
    __pool = None
    def __init__(self,host,user,passwd,db,port,charset):
        # 构造函数，创建数据库连接、游标
        self.coon = OPMysql.getmysqlconn(host,user,passwd,db,port,charset)
        self.cur = self.coon.cursor(cursor=pymysql.cursors.DictCursor)
    # 数据库连接池连接
    @staticmethod
    def getmysqlconn(host,user,passwd,db,port,charset):
        if OPMysql.__pool is None:
            __pool = PooledDB(creator=pymysql, mincached=1, maxcached=20, host=host, user=user, passwd=passwd, db=db,port=port, charset='utf8')
        return __pool.connection()
    # 插入\更新\删除sql
    def op_insert(self, sql):
        insert_num = self.cur.execute(sql)
        self.coon.commit()
        return insert_num
    # 查询
    def op_select(self, sql):
        self.cur.execute(sql)  # 执行sql
        select_res = self.cur.fetchall() #返回结果为字典
        return select_res
    #释放资源
    def dispose(self):
        self.coon.close()
        self.cur.close()
#Sqlserver数据库连接池
class OPSqlserver(object):
    __pool = None
    def __init__(self,dbinfo):
        self.conn = OPSqlserver.getconn(dbinfo)
        self.cursor = self.conn.cursor()
    @staticmethod
    def getconn(dbinfo):
        if OPSqlserver.__pool is None:
            __pool = PooledDB(creator=pymssql, mincached=1, maxcached=20, host=dbinfo["host"], user=dbinfo["user"], passwd=dbinfo["passwd"], db=dbinfo["db"],port=dbinfo["port"], charset='utf8')
        return __pool.connection()
        # 插入\更新\删除sql
    def op_insert(self, sql):
        insert_num = self.cur.execute(sql)
        self.conn.commit()
        return insert_num
    # 查询
    def op_select(self, sql):
        self.cur.execute(sql)  # 执行sql
        select_res = self.cur.fetchall() #返回结果为字典
        return select_res
    #释放资源
    def dispose(self):
        self.conn.close()
        self.cur.close()
#redis数据库连接池
class OPRedis(object):
    __pool = None
    def __init__(self,dbinfo):
        self.pool = OPRedis.getconn(dbinfo)
        self.r = redis.Redis(connection_pool=self.pool)
    @staticmethod
    def getconn(dbinfo):
        if OPRedis.__pool is None:
           __pool = redis.ConnectionPool(host=dbinfo["host"],port=dbinfo["port"],password=dbinfo["password"],db=dbinfo["db"])
        return __pool
    def op_set(self,key,value):
        try:
           self.r.set(key,value)
        except:
           return "Erro"
        return "Success"
    def op_get(self,key):
        try:
           data = self.r.get(key)
        except:
           return "Erro"
        return data
    def op_del(self,key):
        try:
           self.r.delete(key)
        except:
           return "Erro"
        return "Success"

#oracle数据库连接池
class Ora():
    __pool = None  # 连接池对象
    def __init__(self, db_info=None):
        # 连接池方式
        self.db_info = db_info
        self.conn = Ora.__getConn(db_info)
        self.cursor = self.conn.cursor()
    @staticmethod
    def __getConn(db_info):

        # 静态方法，从连接池中取出连接
        if Ora.__pool is None:
            __pool = PooledDB(cx_Oracle,
                              user=db_info['user'],
                              password=db_info['pwd'],
                              dsn="%s:%s/%s" % (db_info['host'], db_info['port'], db_info['sid']),
                              mincached=20,
                              maxcached=200)
        return __pool.connection()

    # 查询表的所有列
    def columns(self, table):
        sql = ["select lower(column_name)column_name \
        from user_tab_columns where table_name=upper('%(table)s')"]
        rows = self.query(''.join(sql) % locals())
        col_list = [k["column_name"] for k in rows]
        # ['sjhm', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'status']
        return col_list

    # 根据表自动创建参数字典
    def create_params(self, table, args={}):
        col_list = self.columns(table)
        params = {}
        for k in col_list:
            if args.has_key(k):
                params[k] = args[k]
        return params

    # 执行sql
    def execute(self, sql, args={}):
        try:
            return self.cursor.execute(sql, args)
        except  Exception as e:
            self.close()
            raise e

    # 批量执行
    def executemany(self, sql, args):
        try:
            return self.cursor.executemany(sql, args)
        except  Exception as e:
            self.close()
            raise e

    # 备份记录,如果没有该表格将自动建表，以log_表名 命名,参数二：操作人工号，参数三：操作说明，
    # 参数四：用于where条件，如 where 字段3=值3 and 字段4=值4，格式{'字段3':'值3','字段4':'值4'}
    def backup(self, table, userid, remark, cond_dict):
        cond_dict = self.create_params(table, cond_dict)
        sql = ["select count(*)cnt FROM user_tables "]
        sql.append(" WHERE table_name = upper('log_%(table)s')")
        rows = self.query("".join(sql) % locals())
        if rows[0]["cnt"] == 0:  # 注意oracle列名大写
            self.execute("create table log_%(table)s as  select * from %(table)s where 1>2 " % locals())
            self.execute(" alter table log_%(table)s add(backup_userid varchar2(40),\
            backup_date date,back_remark varchar2(200))" % locals())
        cond_stmt = ' and '.join(['%s=:%s' % (k, k) for k in cond_dict.keys()])
        upd_sql = "insert into log_%(table)s select t.*,:userid,sysdate,:remark from %(table)s t where %(cond_stmt)s"
        cond_dict['userid'] = userid
        cond_dict['remark'] = remark
        return self.execute(upd_sql % locals(), cond_dict)

    # 执行sql，参数一：sql语句，参数二：参数字典{'字段1'：'值1','字段2':'值2'}
    def query(self, sql, args={}):
        self.execute(sql, args)
        return self.get_rows()

    # 分页查询，参数一：sql语句，参数二：参数字典{'字段1'：'值1','字段2':'值2'}，参数三：页码，参数四：分页大小
    def query_pages(self, sql, args={}, page=1, page_size=30):
        _args, count_args = args, args
        page = int(page)
        # print "page:%s" %(page,)
        # 下一页
        next_page = page_size * page
        # 当前页
        cur_page = page_size * (page - 1)
        if page == 1 or cur_page < 0:
            cur_page = 0
            next_page = page_size
        sql = """SELECT * FROM(
            SELECT ROWNUM RN,T.* FROM(""" + sql + """)T 
            WHERE ROWNUM<=:next_page
            )WHERE RN >=:cur_page """
        count_sql = """
            SELECT COUNT(1)CNT FROM (""" + sql + """)"""
        _args["cur_page"] = cur_page
        _args["next_page"] = next_page
        rows = self.query(sql, _args)
        countrows = self.query(count_sql, count_args)
        return rows, countrows[0]['cnt']

    # oracle的参数名必须使用:代替，如 userid = :userid
    def insert(self, table, column_dict):
        column_dict = self.create_params(table, column_dict)
        keys = ','.join(column_dict.keys())
        values = column_dict.values()
        placeholder = ','.join([':%s' % (v) for v in column_dict.keys()])
        ins_sql = 'INSERT INTO %(table)s (%(keys)s) VALUES (%(placeholder)s)'
        self.execute(ins_sql % locals(), column_dict)

    # 获取序列的下一个值，传入sequence的名称
    def nextval(self, seq):
        self.cursor.execute("SELECT %(seq)s.nextval from dual " % locals())
        result = self.cursor.fetchall()
        return result[0][0]

    # 批量插入数据库，参数一：表名，参数二：['字段1','字段2',...],参数二：[('值1','值2',...),('值1','值2',...)]
    def multi_insert(self, table, columns=[], values=()):
        keys = ','.join(columns)
        placeholder = ','.join([':%s' % (v) for v in columns])
        ins_sql = 'INSERT INTO %(table)s (%(keys)s) VALUES(%(placeholder)s)'
        return self.cursor.executemany(ins_sql % locals(), values)

    # 更新，参数一：表名，参数二用于set 字段1=值1，字段2=值2...格式：{'字段1':'值1','字段2':'值2'},
    # 参数三：用于where条件，如 where 字段3=值3 and 字段4=值4，格式{'字段3':'值3','字段4':'值4'}
    def update(self, table, column_dict={}, cond_dict={}):
        column_dict = self.create_params(table, column_dict)
        cond_dict = self.create_params(table, cond_dict)
        set_stmt = ','.join(['%s=:%s' % (k, k) for k in column_dict.keys()])
        cond_stmt = ' and '.join(['%s=:%s' % (k, k) for k in cond_dict.keys()])
        upd_sql = 'UPDATE %(table)s set %(set_stmt)s where %(cond_stmt)s'
        args = dict(column_dict, **cond_dict)  # 合并成1个
        return self.execute(upd_sql % locals(), args)

    # 删除，参数一：表名，#参数二：用于where条件，如 where 字段3=值3 and 字段4=值4，格式{'字段3':'值3','字段4':'值4'}
    def delete(self, table, cond_dict):
        cond_dict = self.create_params(table, cond_dict)
        cond_stmt = ' and '.join(['%s=:%s' % (k, k) for k in cond_dict.keys()])
        del_sql = 'DELETE FROM %(table)s where %(cond_stmt)s'
        return self.execute(del_sql % locals(), cond_dict)

    # 提取数据，参数一提取的记录数，参数二，是否以字典方式提取。为true时返回：{'字段1':'值1','字段2':'值2'}
    def get_rows(self, size=None, is_dict=True):
        if size is None:
            rows = self.cursor.fetchall()
        else:
            rows = self.cursor.fetchmany(size)
        if rows is None:
            rows = []
        if is_dict:
            dict_rows = []
            dict_keys = [r[0].lower() for r in self.cursor.description]
            for row in rows:
                dict_rows.append(dict(zip(dict_keys, row)))
            rows = dict_rows
        return rows

    # 获取记录数
    def get_rows_num(self):
        return self.cursor.rowcount

    # 提交
    def commit(self):
        self.conn.commit()

    # 回滚
    def rollback(self):
        self.conn.rollback();

    # 销毁
    def __del__(self):
        self.close()

    # 关闭连接
    def close(self):
        self.commit()
        self.cursor.close()
        self.conn.close()
#pgsql数据库连接池
class OPPgsql(object):
    __pool = None
    def __init__(self,dbinfo):
        self.conn = OPPgsql.getconn(dbinfo)
        self.cur = self.conn.cursor()
    @staticmethod
    def getconn(dbinfo):
        if OPPgsql.__pool is None:
           __pool = PooledDB(creator=pymssql, mincached=1, maxcached=20, host=dbinfo["host"], user=dbinfo["user"], passwd=dbinfo["passwd"], db=dbinfo["db"],port=dbinfo["port"], charset='utf8')
        return __pool.connection()
    # 插入\更新\删除sql
    def op_insert(self, sql):
        insert_num = self.cur.execute(sql)
        self.conn.commit()
        return insert_num
    # 查询
    def op_select(self, sql):
        self.cur.execute(sql)  # 执行sql
        select_res = self.cur.fetchall() #返回结果为字典
        return select_res
    #释放资源
    def dispose(self):
        self.conn.close()
        self.cur.close()
#mongodb数据库连接池
#class OPMongo(object):
#    __pool = None
#    def __init(self,dbinfo)
#        self.conn = OPMongo.getconn(dbinfo)
#        self.cur = self.conn.cursor()

