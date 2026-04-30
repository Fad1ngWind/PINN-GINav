# # import pyrtklib as prl
# # #import pyrtklib_debug.build.pyrtklib_debug as prl
# # #import pyrtklib_debug.build.pyrtklib as prl
# # import numpy as np
# # import pymap3d as p3d
# # import pandas as pd
# # import math
# # import os
# # try:
# #     import torch
# #     torch_enable = True
# # except:
# #     torch_enable = False    



# # SYS = {'G':prl.SYS_GPS,'C':prl.SYS_CMP,'E':prl.SYS_GAL,'R':prl.SYS_GLO,'J':prl.SYS_QZS}

# # def enable_multi_gnss(opt_or_nav):
# #     """强制开启多系统"""
# #     SYS_GPS = 0x01
# #     SYS_SBS = 0x02
# #     SYS_GLO = 0x04
# #     SYS_GAL = 0x08
# #     SYS_QZS = 0x10
# #     SYS_CMP = 0x20 # BeiDou
# #     SYS_ALL = SYS_GPS | SYS_GLO | SYS_GAL | SYS_CMP
    
# #     try:
# #         opt_or_nav.navsys = SYS_ALL
# #     except:
# #         pass

# # def memorize_func(func):
# #     cache = {}
# #     def wrapper(index,*args):
# #         if index in cache:
# #             return cache[index]
# #         else:
# #             result = func(*args)
# #             cache[index] = result
# #             return result
# #     return wrapper

# # def arr_select(arr,select,step = 1):
# #     obj_class = type(arr)
# #     n = len(select)*step
# #     arr_sel = obj_class(n)
# #     for i in range(len(select)):
# #         for j in range(step):
# #             arr_sel[i*step+j] = arr[select[i]*step+j]
# #     return arr_sel

# # def arr(src_list,arr_type):
# #     l = len(src_list)
# #     ret = arr_type(l)
# #     for i in range(l):
# #         ret[i]=src_list[i]
# #     return ret

# # def gettgd(sat, nav, type):
# #     sys_name = prl.Arr1Dchar(4)
# #     prl.satno2id(sat,sys_name)
# #     sys = SYS[sys_name.ptr[0]]
# #     eph = nav.eph
# #     geph = nav.geph
# #     if sys == prl.SYS_GLO:
# #         for i in range(nav.ng):
# #             if geph[i].sat == sat:
# #                 break
# #         return 0.0 if i >= nav.ng else -geph[i].dtaun * prl.CLIGHT
# #     else:
# #         for i in range(nav.n):
# #             if eph[i].sat == sat:
# #                 break
# #         return 0.0 if i >= nav.n else eph[i].tgd[type] * prl.CLIGHT

# # def prange(obs, nav, opt, var):
# #     P1, P2, gamma, b1, b2 = 0.0, 0.0, 0.0, 0.0, 0.0
# #     var[0] = 0.0

# #     sat = obs.sat

# #     sys_name = prl.Arr1Dchar(4)
# #     prl.satno2id(sat,sys_name)
# #     sys = SYS[sys_name.ptr[0]]
# #     P1 = obs.P[0]
# #     P2 = obs.P[1]

# #     if P1 == 0.0 or (opt.ionoopt == prl.IONOOPT_IFLC and P2 == 0.0):
# #         return 0.0

# #     # P1-C1, P2-C2 DCB correction
# #     if sys == prl.SYS_GPS or sys == prl.SYS_GLO:
# #         if obs.code[0] == prl.CODE_L1C:
# #             P1 += nav.cbias[sat - 1,1]  # C1->P1
# #         if obs.code[1] == prl.CODE_L2C:
# #             P2 += nav.cbias[sat - 1,2]  # C2->P2

# #     if opt.ionoopt == prl.IONOOPT_IFLC:  # dual-frequency
# #         if sys == prl.SYS_GPS or sys == prl.SYS_QZS:  # L1-L2, G1-G2
# #             gamma = (prl.FREQ1 / prl.FREQ2) ** 2
# #             return (P2 - gamma * P1) / (1.0 - gamma)
# #         elif sys == prl.SYS_GLO:  # G1-G2
# #             gamma = (prl.FREQ1_GLO / prl.FREQ2_GLO) ** 2
# #             return (P2 - gamma * P1) / (1.0 - gamma)
# #         elif sys == prl.SYS_GAL:  # E1-E5b
# #             gamma = (prl.FREQ1 / prl.FREQ7) ** 2
# #             if prl.getseleph(prl.SYS_GAL):  # F/NAV
# #                 P2 -= gettgd(sat, nav, 0) - gettgd(sat, nav, 1)  # BGD_E5aE5b
# #             return (P2 - gamma * P1) / (1.0 - gamma)
# #         elif sys == prl.SYS_CMP:  # B1-B2
# #             gamma = (((prl.FREQ1_CMP if obs.code[0] == prl.CODE_L2I else prl.FREQ1) / prl.FREQ2_CMP) ** 2)
# #             b1 = gettgd(sat, nav, 0) if obs.code[0] == prl.CODE_L2I else gettgd(sat, nav, 2) if obs.code[0] == prl.CODE_L1P else gettgd(sat, nav, 2) + gettgd(sat, nav, 4)  # TGD_B1I / TGD_B1Cp / TGD_B1Cp+ISC_B1Cd
# #             b2 = gettgd(sat, nav, 1)  # TGD_B2I/B2bI (m)
# #             return ((P2 - gamma * P1) - (b2 - gamma * b1)) / (1.0 - gamma)
# #         elif sys == prl.SYS_IRN:  # L5-S
# #             gamma = (prl.FREQ5 / prl.FREQ9) ** 2
# #             return (P2 - gamma * P1) / (1.0 - gamma)
# #     else:  # single-freq (L1/E1/B1)
# #         var[0] = 0.3 ** 2
        
# #         if sys == prl.SYS_GPS or sys == prl.SYS_QZS:  # L1
# #             b1 = gettgd(sat, nav, 0)  # TGD (m)
# #             return P1 - b1
# #         elif sys == prl.SYS_GLO:  # G1
# #             gamma = (prl.FREQ1_GLO / prl.FREQ2_GLO) ** 2
# #             b1 = gettgd(sat, nav, 0)  # -dtaun (m)
# #             return P1 - b1 / (gamma - 1.0)
# #         elif sys == prl.SYS_GAL:  # E1
# #             b1 = gettgd(sat, nav, 0) if prl.getseleph(prl.SYS_GAL) else gettgd(sat, nav, 1)  # BGD_E1E5a / BGD_E1E5b
# #             return P1 - b1
# #         elif sys == prl.SYS_CMP:  # B1I/B1Cp/B1Cd
# #             b1 = gettgd(sat, nav, 0) if obs.code[0] == prl.CODE_L2I else gettgd(sat, nav, 2) if obs.code[0] == prl.CODE_L1P else gettgd(sat, nav, 2) + gettgd(sat, nav, 4)  # TGD_B1I / TGD_B1Cp / TGD_B1Cp+ISC_B1Cd
# #             return P1 - b1
# #         elif sys == prl.SYS_IRN:  # L5
# #             gamma = (prl.FREQ9 / prl.FREQ5) ** 2
# #             b1 = gettgd(sat, nav, 0)  # TGD (m)
# #             return P1 - gamma * b1
# #     return P1

# # def nextobsf(obs,i):
# #     n = 0
# #     while i+n < obs.n:
# #         tt = prl.timediff(obs.data[i+n].time,obs.data[i].time)
# #         if abs(tt) > 0.05:
# #             break
# #         n+=1
# #     return n

# # def get_sat_pos(obsd, n, nav):
# #     svh = prl.Arr1Dint(prl.MAXOBS)
# #     rs = prl.Arr1Ddouble(6 * n)
# #     dts = prl.Arr1Ddouble(2 * n)
# #     var = prl.Arr1Ddouble(1 * n)
    
# #     # 计算卫星位置
# #     prl.satposs(obsd[0].time, obsd.ptr, n, nav, 0, rs, dts, var, svh)
    
# #     noeph = []
# #     for i in range(n):
# #         # 取出 XYZ 坐标
# #         x = rs[6*i]
# #         y = rs[6*i+1]
# #         z = rs[6*i+2]
        
# #         # 计算距离地心的距离
# #         dist = np.sqrt(x*x + y*y + z*z)
        
# #         # === 核心修改：严格的物理检查 ===
# #         # 1. 检查是否为 NaN (无效值)
# #         if np.isnan(dist):
# #             noeph.append(i)
# #             continue
            
# #         # 2. 检查是否在地心附近 (全0异常)
# #         # 地球半径 ~6371km。如果卫星距离地心小于 1000米，绝对是错误的。
# #         if dist < 1000.0:
# #             noeph.append(i)
# #             continue
            
# #         # 3. 检查是否飞出太阳系 (防爆)
# #         # GNSS 卫星轨道高度约 20,000km ~ 36,000km。
# #         # 如果距离地心超过 50,000km (5e7米)，说明轨道参数错乱。
# #         if dist > 50000000.0:
# #             noeph.append(i)
# #             continue
            
# #     # 筛选有效数据返回
# #     nrs = []
# #     for i in range(6 * n):
# #         # 这是一个扁平数组，我们需要保留有效卫星的所有 6 个参数 (Pos+Vel)
# #         # 这种写法比较笨拙，我们用原来的 arr_select 逻辑更稳妥
# #         pass 

# #     # 使用你原有的 arr_select 逻辑来生成返回数组，保持兼容性
# #     mask = list(set(range(n)) - set(noeph))
# #     nrs = arr_select(rs, mask, 6)
# #     var = arr_select(var, mask)
# #     # dts 也要筛选
# #     ndts = arr_select(dts, mask, 2)
    
# #     return nrs, noeph, ndts, var

# # def split_obs(obs, dt_th=0.05): # 默认容差改为 0.05 秒
# #     obss = []
# #     n = obs.n
# #     if n == 0: return obss
    
# #     i = 0
# #     while i < n:
# #         # 当前历元的起始时间
# #         tt = obs.data[i].time
        
# #         # 向后寻找所有在这个时间容差范围内的数据
# #         j = i
# #         while j < n:
# #             # 计算时间差
# #             dt = prl.timediff(obs.data[j].time, tt)
# #             if abs(dt) > dt_th: # 如果超过容差，说明是下一个历元了
# #                 break
# #             j += 1
        
# #         # 创建一个新的 obs 对象，包含从 i 到 j 的所有数据
# #         count = j - i
# #         if count > 0:
# #             tmp_obs = prl.obs_t()
# #             tmp_obs.n = count
# #             tmp_obs.data = prl.Arr1Dobsd_t(count)
# #             for k in range(count):
# #                 tmp_obs.data[k] = obs.data[i + k]
# #             obss.append(tmp_obs)
        
# #         # 移动指针
# #         i = j
        
# #     return obss


# # def get_common_obs(obs):
# #     m = obs.n
# #     tmp1 = {}
# #     tmp2 = {}
# #     for i in range(m):
# #         if obs.data[i].rcv == 1:
# #             tmp1[obs.data[i].sat-1] = obs.data[i]
# #         else:
# #             tmp2[obs.data[i].sat-1] = obs.data[i]
# #     common = []
# #     index = []
# #     tmp1keys = list(tmp1.keys())
# #     for j in range(len(tmp1keys)):
# #         i = tmp1keys[j]
# #         if i in tmp2:
# #             if tmp1[i].P[0]!=0 and tmp2[i].P[0]!=0:
# #                 common.append(i)
# #                 index.append(j)
# #     obsd1 = prl.Arr1Dobsd_t(len(common))
# #     obsd2 = prl.Arr1Dobsd_t(len(common))
# #     for i in range(len(common)):
# #         obsd1[i] = tmp1[common[i]]
# #         obsd2[i] = tmp2[common[i]]
# #     return obsd1,obsd2,common,index


# # def rov2head(obs,n):
# #     r_head = prl.Arr1Dobsd_t(n)
# #     j = 0
# #     for i in range(n):
# #         if obs[i].rcv == 1:
# #             r_head[j] = obs[i]
# #             j+=1
# #     for i in range(n):
# #         if obs[i].rcv == 2:
# #             r_head[j] = obs[i]
# #             j+=1
# #     return r_head

# # def get_sat_id(no):
# #     tmp = prl.Arr1Dchar(4)
# #     prl.satno2id(no,tmp)
# #     return tmp[0]

# # def get_max_sys_el(obsd,n,sol_spp):
# #     azel = sol_spp['data']['azel']
# #     ex = sol_spp['data']['exclude']
# #     mask = list(set(range(n))-set(ex))
# #     azel = arr_select(azel,mask,2)
# #     ms = {sys:[-1,0] for sys in SYS}
# #     for i in range(n):
# #         name = get_sat_id(obsd[i].sat)
# #         sys = name[0]
# #         el = azel[i*2+1]
# #         if el > ms[sys][1]:
# #             ms[sys][0] = i
# #             ms[sys][1] = el
# #     return ms



# # def get_rtklib_pnt(obs,nav,prcopt,mode):
# #     if mode == "SPP":
# #         sol,sat,azel,msg = get_obs_pnt(obs,nav,prcopt)
# #         if msg.ptr and "chi-square error" not in msg.ptr and "gdop error" not in msg.ptr:
# #             return sol,False
# #         else:
# #             return sol,True
# #     if mode == "DGNSS":
# #         rtk = get_obs_rtk(obs,nav,prcopt)
# #         # return rtk.sol,True
# #         msg = rtk.errbuf.ptr
# #         if msg and "ambiguity validation failed" not in msg and "chi-square error" not in msg and "slip detected forward" not in msg and "slip detected half-cyc" not in msg and "no double-differenced residual" not in msg:
# #             return rtk.sol,False
# #         else:
# #             return rtk.sol,True

# # # this calls the pntpos in rtklib
# # def get_obs_pnt(obs,nav,prcopt):
# #     m = obs.n
# #     sol = prl.sol_t()
# #     sat = prl.Arr1Dssat_t(prl.MAXSAT)
# #     sol.time = obs.data[0].time
# #     msg = prl.Arr1Dchar(100)
# #     azel = prl.Arr1Ddouble(m*2)
# #     prl.pntpos(obs.data.ptr,obs.n,nav,prcopt,sol,azel,sat.ptr,msg)
# #     return sol,sat,azel,msg

# # def get_obs_rtk(obs,nav,prcopt):
# #     rtk = prl.rtk_t()
# #     prl.rtkinit(rtk,prcopt)
# #     #rtk_obs = rov2head(obs.data,obs.n)
# #     prl.rtkpos(rtk,obs.data.ptr,obs.n,nav)
# #     return rtk


# # def read_obs(rcv, eph, ref=None):
# #     obs = prl.obs_t()
# #     nav = prl.nav_t()
# #     sta = prl.sta_t()
    
# #     # 1. 读取 Rover
# #     print(f"Reading Rover data: {rcv}")
# #     if type(rcv) is list:
# #         for r in rcv:
# #             prl.readrnx(r, 1, "", obs, nav, sta)
# #     else:
# #         prl.readrnx(rcv, 1, "", obs, nav, sta)
        
# #     # 2. 读取 Base
# #     if ref:
# #         print(f"Reading Base Station data: {ref}")
# #         if type(ref) is list:
# #             for r in ref:
# #                 prl.readrnx(r, 2, "", obs, nav, sta)
# #         else:
# #             prl.readrnx(ref, 2, "", obs, nav, sta)

# #     # 3. 读取星历 (支持 SP3轨道 + CLK钟差 + RINEX广播)
# #     if type(eph) is list:
# #         files = eph
# #     else:
# #         files = [eph]
        
# #     for f in files:
# #         print(f"Loading Ephemeris file: {f}")
        
# #         # 识别 .sp3 (精密轨道)
# #         if f.lower().endswith('.sp3'):
# #             print(">>> Type: SP3 (Precise Orbit)")
# #             prl.readsp3(f, nav, 0)
            
# #         # 识别 .clk (精密钟差) - 新增支持！
# #         elif f.lower().endswith('.clk'):
# #             print(">>> Type: RINEX CLK (Precise Clock)")
# #             # 尝试调用 readrnxc，如果pyrtklib没导出该函数，则尝试用readrnx
# #             try:
# #                 prl.readrnxc(f, nav)
# #             except AttributeError:
# #                 # 兼容性备选：有些版本的封装直接用 readrnx 也能读 clock
# #                 prl.readrnx(f, 2, "", obs, nav, sta)
                
# #         # 默认当作广播星历 (RINEX Nav)
# #         else:
# #             print(">>> Type: Broadcast Ephemeris")
# #             prl.readrnx(f, 2, "", obs, nav, sta)
            
# #     return obs, nav, sta
        
# # def get_obs_utc_time(obstime):
# #     return obstime.time+obstime.sec-18

# # def get_obs_time(obstime):
# #     return obstime.time+obstime.sec

# # def H_matrix_prl(satpos,rp,dts,time,nav,sats,exclude = []):
# #     ex = [] # exclude sat order
# #     n = int(len(satpos)/6)
# #     Ht = []
# #     Rt = []
# #     e = prl.Arr1Ddouble(3)
# #     rr = prl.Arr1Ddouble(3)
# #     rr[0] = rp[0]
# #     rr[1] = rp[1]
# #     rr[2] = rp[2]
# #     azel = prl.Arr1Ddouble(n*2)
# #     pos = prl.Arr1Ddouble(3)
# #     prl.ecef2pos(rr,pos)
    
# #     dion = prl.Arr1Ddouble(1)
# #     vion = prl.Arr1Ddouble(1)
# #     dtrp = prl.Arr1Ddouble(1)
# #     vtrp = prl.Arr1Ddouble(1)

# #     vels = []
# #     vions = []
# #     vtrps = []

# #     sysname = prl.Arr1Dchar(4)
# #     count = {'G':0,'C':0,'E':0,'R':0}
# #     for i in range(n):
# #         if i in exclude:
# #             ex.append(i)
# #             continue
# #         sp = np.array(satpos[i*6+0:i*6+3])
# #         #r = np.linalg.norm(sp-rp[:3])
# #         r = prl.geodist(satpos[i*6:i*6+3],rr,e)
# #         azel_tmp = prl.Arr1Ddouble(2)
# #         prl.satazel(pos,e,azel_tmp)
# #         azel[i*2] = azel_tmp[0]
# #         azel[i*2+1] = azel_tmp[1]

# #         if azel_tmp[1] < 0:
# #             ex.append(i)
# #             continue
# #         prl.ionocorr(time,nav,sats[i],pos,azel_tmp,prl.IONOOPT_BRDC,dion,vion)
# #         prl.tropcorr(time,nav,pos,azel_tmp,prl.TROPOPT_SAAS,dtrp,vtrp)
# #         vions.append(vion.ptr)
# #         vtrps.append(vtrp.ptr)
# #         prl.satno2id(sats[i],sysname)
# #         vel = varerr(azel_tmp[1],sysname.ptr[0])
# #         vels.append(vel)
# #         if 'G' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,1,0,0,0])
# #             Rt.append(r+rp[3]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['G']+=1
# #         elif 'C' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,0,1,0,0])
# #             Rt.append(r+rp[4]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['C']+=1
# #         elif 'E' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,0,0,1,0])
# #             Rt.append(r+rp[5]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['E']+=1
# #         elif 'R' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,0,0,0,1])
# #             Rt.append(r+rp[6]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['R']+=1
# #     if n-len(ex) > 3:
# #         H = np.vstack(Ht).astype(np.float64)
# #         R = np.vstack(Rt).astype(np.float64)
# #     else:
# #         H = np.zeros((1,7))
# #         R = np.zeros((1,1))
# #         #return H,R,azel,ex,np.array([]),count,vels,vions,vtrps
# #     sysinfo = np.where(np.any(H!=0,axis=0))[0]
# #     H = H[:,sysinfo]
# #     return H,R,azel,ex,sysinfo,count,vels,vions,vtrps

# # def wls_solve(H,z,w = None,b = None):
# #     if w is None:
# #         w = np.eye(len(H))
# #     if b is None:
# #         b = np.zeros((len(H),1))
# #     t1 = np.matmul(H.T,w)
# #     t2 = np.matmul(t1,H)
# #     t3 = np.matmul(np.linalg.inv(t2),H.T)
# #     t4 = np.matmul(t3,w)
# #     x = np.matmul(t4,(z-b))
# #     return x


# # def get_dgnss_pos(obs,sta,nav):
# #     maxiter = 20
# #     ms_info = {i:[] for i in SYS}
# #     MS = {i:-1 for i in SYS}
# #     n_o1 = np.sum(np.array([obs.data[i].rcv for i in range(obs.n)])==1)
# #     o1,o2,com,index1 = get_common_obs(obs)
# #     rs, noeph, dts, var = get_sat_pos(o1,len(com),nav)
# #     if noeph:
# #         mask = list(set(range(len(com)))-set(noeph))
# #         o1 = arr_select(o1,mask)
# #         o2 = arr_select(o2,mask)
# #         com = list(np.array(com)[mask])
# #     o1_obs = prl.obs_t()
# #     o1_obs.data = obs.data[:n_o1]
# #     o1_obs.n = n_o1
# #     o1_obs.nmax = n_o1
# #     spp_sol = get_wls_pnt_pos(o1_obs,nav)
# #     ms = get_max_sys_el(o1,len(com),spp_sol)
# #     res = []
# #     sys_map = []
# #     for i in range(len(com)):
# #         name = get_sat_id(o1[i].sat)
# #         sys = name[0]
# #         no = ms[sys][0]
# #         if i == no:
# #             sys_map.append(sys)
# #             continue
# #         r21 = np.linalg.norm(np.array(rs[no*6+0:no*6+3])-np.array(sta.pos)).astype('float64')
# #         r22 = np.linalg.norm(np.array(rs[i*6+0:i*6+3])-np.array(sta.pos)).astype('float64')
# #         dp1 = o1[i].P[0] - o1[no].P[0]
# #         dp2 = o2[i].P[0] - o2[no].P[0]
# #         r = dp1-dp2+(r22-r21)
# #         res.append(r)
# #         sys_map.append(sys)
# #     res = np.array(res)
# #     dx = np.array([1000,1000,1000],dtype=np.double)
# #     p = np.array([0,0,0],dtype=np.double)
# #     i = 0
# #     while np.linalg.norm(dx) > 0.01 and i < maxiter:
# #         H,R = DD_H_matrix(rs,p,ms,sys_map)
# #         resd = res.reshape((-1,1))-R
# #         dx = wls_solve(H,resd)
# #         p = p+dx.squeeze()
# #         i+=1
# #     return p,resd
    

        
# # def DD_H_matrix(satpos,p00,ms,sys_map):
# #     n = int(len(satpos)/6)
# #     Ht = []
# #     Rt = []
# #     b_flag = False
# #     msns = [ms[sys][0] for sys in ms]
# #     for i in range(n):
# #         if i in msns:
# #             continue
# #         msn = ms[sys_map[i]][0]
# #         p0 = np.array(satpos[msn*6+0:msn*6+3])
# #         r0 = np.linalg.norm(p0-p00)
# #         p = np.array(satpos[i*6+0:i*6+3])
# #         r = np.linalg.norm(p-p00)
# #         Ht.append(np.array([-(p[0]-p00[0])/r-(-(p0[0]-p00[0]))/r0,-(p[1]-p00[1])/r-(-(p0[1]-p00[1]))/r0,-(p[2]-p00[2])/r-(-((p0[2]-p00[2]))/r0)]))
# #         Rt.append(r-r0)
# #     H = np.vstack(Ht)
# #     R = np.vstack(Rt)
# #     return H,R



# # def get_wls_pnt_pos(o, nav, exsatids=[], SNR=0, EL=0, RESD=10000):
# #     """
# #     [Robust] 增强版单点定位 (SPP) v7 - 最终稳定版
# #     核心改进：
# #     1. 【重心初始化】：不再从 (0,0,0) 开始，而是用卫星重心的地表投影点作为初值，避免对流层模型崩溃。
# #     2. 【分步收敛】：前两次迭代不加权，先拉到大致位置，再开启加权。
# #     3. 【保留手动对齐】：沿用 v5 的手动切片逻辑，保证程序稳定。
# #     """
# #     maxiter = 10
# #     EARTH_RAD = 6371000.0 # 地球半径 (米)
    
# #     # 1. 基础筛选
# #     if o.n < 4:
# #         return {"status":False, "pos":np.zeros(7), "msg":"not enough obs (<4)", "data":{}}
    
# #     rs_compact, noeph, dts_compact, var_compact = get_sat_pos(o.data, o.n, nav)
    
# #     # 构建映射
# #     org_to_rs_map = {}
# #     rs_ptr = 0
# #     for i in range(o.n):
# #         if i not in noeph:
# #             org_to_rs_map[i] = rs_ptr
# #             rs_ptr += 1
            
# #     # 3. 筛选有效卫星 & 计算初始位置
# #     obs_data = []
# #     sysname = prl.Arr1Dchar(4)
# #     valid_P_values = []
# #     valid_sat_pos_sum = np.zeros(3) # 用于计算重心
# #     valid_sat_count = 0
    
# #     for i in range(o.n):
# #         d = o.data[i]
# #         prl.satno2id(d.sat, sysname)
# #         if (i in noeph) or (d.P[0] == 0) or (d.sat in exsatids) or \
# #            (d.SNR[0] < SNR*1e3) or (sysname.ptr[0] not in ['G','C','R','E']):
# #             continue
        
# #         obs_data.append(i)
# #         valid_P_values.append(d.P[0])
        
# #         # 累加卫星位置用于计算重心
# #         rs_idx = org_to_rs_map[i]
# #         p_base = rs_idx * 6
# #         sat_xyz = np.array([rs_compact[p_base], rs_compact[p_base+1], rs_compact[p_base+2]])
# #         # 简单过滤掉 (0,0,0) 的异常卫星位置
# #         if np.linalg.norm(sat_xyz) > 1000:
# #             valid_sat_pos_sum += sat_xyz
# #             valid_sat_count += 1
        
# #     if len(obs_data) < 5: 
# #         return {"status":False, "pos":np.zeros(7), "msg":f"valid sats < 5 ({len(obs_data)})", "data":{}}

# #     # === [关键改进] 智能初始化位置 ===
# #     x_init = np.zeros(7)
    
# #     # 1. 位置初始化：卫星重心的地表投影
# #     if valid_sat_count > 0:
# #         mean_pos = valid_sat_pos_sum / valid_sat_count
# #         norm_mean = np.linalg.norm(mean_pos)
# #         if norm_mean > 0:
# #             # 投影到地球表面
# #             x_init[:3] = (mean_pos / norm_mean) * EARTH_RAD
# #         else:
# #             x_init[:3] = np.array([EARTH_RAD, 0, 0]) # 极其罕见的兜底
# #     else:
# #         x_init[:3] = np.array([EARTH_RAD, 0, 0])

# #     # 2. 钟差初始化
# #     # P = dist + dt * c  =>  dt = (P - dist) / c
# #     # 这里我们用距离单位 (meter) 表示钟差，所以 x[3] = P - dist
# #     if len(valid_P_values) > 0:
# #         avg_P = np.mean(valid_P_values)
# #         # 估算几何距离：卫星平均高度约 20200km，也就是距离地表 2.02e7 米
# #         # GPS轨道半径 ~26560km, 地球 ~6371km. 垂直距离 ~2e7.
# #         # 但考虑到仰角，平均距离通常在 2.2e7 ~ 2.4e7 之间
# #         x_init[3] = avg_P - 2.2e7 

# #     # 4. 迭代解算 (RAIM 循环)
# #     current_obs_indices = obs_data.copy()
# #     max_removals = max(1, len(obs_data) - 5) 
    
# #     for attempt in range(max_removals + 1): 
# #         if len(current_obs_indices) < 5:
# #             return {"status":False, "pos":np.zeros(7), "msg":"RAIM: sats dropped below 5", "data":{}}

# #         x = x_init.copy() # 重置初值
# #         wls_converged = False
# #         final_resd = None
# #         active_indices_for_raim = []
        
# #         for iter_wls in range(maxiter):
# #             # --- 构建数据 ---
# #             input_sats = []     
# #             input_rs_list = []  
# #             input_dts_list = []
# #             active_indices_temp = []
            
# #             for idx in current_obs_indices:
# #                 if idx not in org_to_rs_map: continue
# #                 rs_idx = org_to_rs_map[idx]
# #                 p_base = rs_idx * 6
# #                 input_rs_list.extend([rs_compact[p_base + k] for k in range(6)])
# #                 input_dts_list.extend([dts_compact[rs_idx*2], dts_compact[rs_idx*2+1]])
# #                 input_sats.append(o.data[idx].sat)
# #                 active_indices_temp.append(idx)

# #             if len(input_sats) < 4: break

# #             input_rs_np = np.array(input_rs_list, dtype=np.float64)
            
# #             try:
# #                 H_raw, R_raw, azel, ex_internal, sysinfo, _, vels, vions, vtrps = H_matrix_prl(
# #                     input_rs_np, x, np.array(input_dts_list), o.data[0].time, nav, input_sats, []
# #                 )
# #             except Exception:
# #                 break 
            
# #             # --- 对齐 P ---
# #             P_aligned = []
# #             R_aligned = []
# #             H_aligned = []
# #             err_var_aligned = []
# #             current_iter_indices = []
            
# #             valid_ptr = 0 
# #             for k, sat_id in enumerate(input_sats):
# #                 if k in ex_internal: continue
# #                 if valid_ptr >= H_raw.shape[0]: break
                
# #                 original_idx = active_indices_temp[k]
# #                 d = o.data[original_idx]
# #                 vmeas = prl.Arr1Ddouble(1)
# #                 P_val = prange(d, nav, prl.prcopt_default, vmeas)
                
# #                 if P_val != 0:
# #                     P_aligned.append(P_val)
# #                     R_aligned.append(R_raw[valid_ptr])
# #                     H_aligned.append(H_raw[valid_ptr])
                    
# #                     # 误差模型
# #                     total_err = vels[valid_ptr] + vions[valid_ptr] + vtrps[valid_ptr] + 10.0
# #                     err_var_aligned.append(total_err)
# #                     current_iter_indices.append(original_idx)
                
# #                 valid_ptr += 1

# #             if len(P_aligned) < 4: break
            
# #             P_vec = np.array(P_aligned)
# #             R_vec = np.array(R_aligned) 
# #             H_mat = np.array(H_aligned) 
            
# #             y = P_vec - R_vec.squeeze()
            
# #             # [鲁棒改进] 前两轮迭代使用等权，防止初始位置不好时被坏卫星的方差带偏
# #             if iter_wls < 2:
# #                 W = np.eye(len(y))
# #             else:
# #                 W = np.diag(1.0 / np.array(err_var_aligned))
            
# #             try:
# #                 H_w = H_mat.T @ W
# #                 Q = np.linalg.inv(H_w @ H_mat)
# #                 dx = Q @ H_w @ y
# #             except np.linalg.LinAlgError:
# #                 break 

# #             # 限制更新步长，防止飞出地球 (Max step 100km)
# #             dx_pos_norm = np.linalg.norm(dx[:3])
# #             if dx_pos_norm > 100000:
# #                 scale = 100000 / dx_pos_norm
# #                 dx[:3] *= scale
            
# #             x[sysinfo] += dx.squeeze()
# #             final_resd = y
# #             active_indices_for_raim = current_iter_indices
            
# #             # 判敛
# #             if np.linalg.norm(dx[:3]) < 0.1:
# #                 wls_converged = True
# #                 break
        
# #         # 结果检查
# #         if wls_converged:
# #             r_xyz = np.linalg.norm(x[:3])
# #             # 检查是否在地球表面附近 (6000-7000km)
# #             if 6000000 < r_xyz < 7000000: 
# #                  return {
# #                      "status": True, 
# #                      "pos": x, 
# #                      "msg": "success", 
# #                      "data": {"residual": final_resd} 
# #                  }
        
# #         # RAIM 剔除
# #         if final_resd is not None and len(final_resd) > 5:
# #             bad_idx_in_resd = np.argmax(np.abs(final_resd))
# #             if bad_idx_in_resd < len(active_indices_for_raim):
# #                 real_bad_idx = active_indices_for_raim[bad_idx_in_resd]
# #                 if real_bad_idx in current_obs_indices:
# #                     current_obs_indices.remove(real_bad_idx)
# #                 else:
# #                     break
# #             else:
# #                 break 
# #         else:
# #             break 

# #     # 最终尝试：如果最后一次结果在地球表面，也算成功
# #     r_last = np.linalg.norm(x[:3])
# #     if 6300000 < r_last < 6500000:
# #          return {"status": True, "pos": x, "msg": "success (fallback)", "data": {"residual": final_resd}}

# #     return {"status":False, "pos":x, "msg":"RAIM failed completely", "data":{}}

# # def get_sat_pos(obsd, n, nav, SRC_dts=False):
# #     svh = prl.Arr1Dint(prl.MAXOBS)
# #     rs = prl.Arr1Ddouble(6 * n)
# #     dts = prl.Arr1Ddouble(2 * n)
# #     var = prl.Arr1Ddouble(1 * n)

# #     # === Debug: 检查轨道参数是否为 0 ===
# #     if not hasattr(get_sat_pos, "has_checked_orbit"):
# #         print("\n" + "="*40)
# #         print(">>> 轨道参数体检 (Orbit Parameter Check) <<<")
        
# #         # 找一条 GPS 星历看看数据对不对
# #         found_valid = False
# #         for i in range(nav.n):
# #             eph = nav.eph[i]
# #             # 简单判断：半长轴 A 必须很大 (地球半径6378km，卫星通常20000km+)
# #             # 注意：A = sqrtA * sqrtA
# #             # 我们检查 eph.A (RTKLIB 内部存储的是 A，不是 sqrtA)
# #             if eph.A > 1000000: 
# #                 sat_id_char = prl.Arr1Dchar(4)
# #                 prl.satno2id(eph.sat, sat_id_char)
# #                 print(f"✅ 发现正常星历: {sat_id_char.ptr}")
# #                 print(f"   - A (半长轴) : {eph.A:.2f} 米 (正常)")
# #                 print(f"   - e (离心率) : {eph.e:.6f}")
# #                 print(f"   - i0 (倾角)  : {eph.i0:.4f}")
# #                 found_valid = True
# #                 break
        
# #         if not found_valid:
# #             print("❌ 严重警告：所有星历的半长轴 A 都似乎小于 1e6！")
# #             print("   原因：generate_rinex 脚本可能写入了 0.0，或者计算 sqrt(A) 出错。")
# #             if nav.n > 0:
# #                 print(f"   抽查第一条星历 A 值: {nav.eph[0].A}")
        
# #         print("="*40 + "\n")
# #         get_sat_pos.has_checked_orbit = True
# #     # ====================================

# #     # 调用核心计算
# #     # 强制使用 eph_opt=0 (广播星历)
# #     prl.satposs(obsd[0].time, obsd.ptr, n, nav, 0, rs, dts, var, svh)

# #     noeph = []
# #     for i in range(n):
# #         # 检查算出来的坐标是不是 (0,0,0)
# #         if np.linalg.norm([rs[6*i], rs[6*i+1], rs[6*i+2]]) < 1e-1:
# #             noeph.append(i)

# #     # 统计失败情况
# #     if len(noeph) == n:
# #         # 为了防止日志爆炸，只打印前几次失败
# #         if not hasattr(get_sat_pos, "fail_counter"):
# #             get_sat_pos.fail_counter = 0
        
# #         if get_sat_pos.fail_counter < 3:
# #             print(f"[Warning] SatPos calc failed for all {n} sats at {obsd[0].time.time}. (Matches: {nav.n})")
# #             get_sat_pos.fail_counter += 1

# #     mask = list(set(range(n)) - set(noeph))
# #     nrs = arr_select(rs, mask, 6)
# #     var = arr_select(var, mask)
# #     if not SRC_dts:
# #         ndts = arr_select(dts, mask, 2)
# #     else:
# #         ndts = dts
# #     return nrs, noeph, ndts, var

# # def varerr(el,sys):
# #     if sys in ['R']:
# #         fact = 1.5
# #     else:
# #         fact = 1
# #     if el < 5*prl.D2R:
# #         el = 5*prl.D2R
# #     err = prl.prcopt_default.err
# #     varr=(err[0]**2)*((err[1]**2)+(err[2])/np.sin(el))
# #     return (fact**2)*varr

# # def get_nlos_wls_pnt_pos(o,nav,nlos,exsatids=[]):
# #     maxiter = 10
# #     if o.n < 4:
# #         return {"status":False,"pos":np.array([0,0,0,0]),"msg":"no enough observations","data":{}}
# #     rs,noeph,dts,var = get_sat_pos(o.data,o.n,nav)
# #     w = 1/np.sqrt(np.array(var))
# #     # if noeph :
# #     #     print('some sats without ephemeris')
# #     prs = []
# #     exclude = []
# #     sats = []
# #     opt = prl.prcopt_default
# #     skip = 0
# #     sysname = prl.Arr1Dchar(4)
# #     vmeas = prl.Arr1Ddouble(1)
# #     for ii in range(o.n):
# #         #print(ii,o.n)
# #         if ii in noeph:
# #             skip+=1
# #             continue
# #         obsd = o.data[ii]
# #         pii = obsd.P[0] #only process L1
# #         prl.satno2id(obsd.sat,sysname)
# #         if  pii == 0 or obsd.sat in exsatids or sysname.ptr[0] not in ['G','C','R','E']:
# #             exclude.append(ii-skip)
# #             prs.append(0)
# #             sats.append(obsd.sat)
# #             continue
# #         pii = prange(obsd,nav,opt,vmeas)
# #         prs.append(pii)
# #         sats.append(obsd.sat)
# #         var[ii-skip] += vmeas.ptr
# #     if len(prs)<4:
# #         return {"status":False,"pos":np.array([0,0,0,0]),"msg":"no enough observations","data":{}}
# #     prs = np.vstack(prs)
# #     p = np.array([0,0,0,0,0,0,0],dtype=np.float64)
# #     dp = np.array([100,100,100],dtype=np.float64)
# #     iii = 0 
# #     var = np.array(var)
# #     #W = np.eye(o.n-len(exclude))
# #     b = np.zeros((o.n-len(exclude),1))
# #     while np.linalg.norm(dp)>0.0001 and iii < maxiter:
# #         H,R,azel,ex,sysinfo,syscount,vels,vions,vtrps = H_matrix_prl_nlos(rs,p,dts,o.data[0].time,nav,sats,nlos,exclude)
# #         inc = set(range(o.n-len(noeph)))-set(ex)
# #         if len(inc) < 4:
# #             iii+=1
# #             continue
# #         tmp_var = np.delete(var,ex)
# #         tmp_var = tmp_var+np.array(vels)+np.array(vions)+np.array(vtrps)
# #         w = 1/np.sqrt(tmp_var)
# #         W = np.diag(w)
# #         resd = prs[list(inc)] - R
# #         dp = wls_solve(H,resd,W)
# #         p[sysinfo] = p[sysinfo]+dp.squeeze()
# #         iii+=1
# #     if iii >= 10:
# #         return {"status":False,"pos":p,"msg":"over max iteration times","data":{"residual":resd}}
# #     if np.sqrt((resd*resd).sum()) > 1000:
# #         return {"status":False,"pos":p,"msg":"residual too large","data":{"residual":resd}}
# #     H,R,azel,ex,sysinfo,syscount,vels,vions,vtrps = H_matrix_prl(rs,p,dts,o.data[0].time,nav,sats,exclude)
# #     return {"status":True,"pos":p,"msg":"success","data":{"residual":resd,'azel':azel,"exclude":ex,"eph":rs,}}


# # def H_matrix_prl_nlos(satpos,rp,dts,time,nav,sats,nlos,exclude = []):
# #     ex = [] # exclude sat order
# #     n = int(len(satpos)/6)
# #     Ht = []
# #     Rt = []
# #     e = prl.Arr1Ddouble(3)
# #     rr = prl.Arr1Ddouble(3)
# #     rr[0] = rp[0]
# #     rr[1] = rp[1]
# #     rr[2] = rp[2]
# #     azel = prl.Arr1Ddouble(n*2)
# #     pos = prl.Arr1Ddouble(3)
# #     prl.ecef2pos(rr,pos)
    
# #     dion = prl.Arr1Ddouble(1)
# #     vion = prl.Arr1Ddouble(1)
# #     dtrp = prl.Arr1Ddouble(1)
# #     vtrp = prl.Arr1Ddouble(1)

# #     vels = []
# #     vions = []
# #     vtrps = []

# #     sysname = prl.Arr1Dchar(4)
# #     count = {'G':0,'C':0,'E':0,'R':0}
# #     for i in range(n):
# #         if i in exclude:
# #             ex.append(i)
# #             continue
# #         sp = np.array(satpos[i*6+0:i*6+3])
# #         #r = np.linalg.norm(sp-rp[:3])
# #         r = prl.geodist(satpos[i*6:i*6+3],rr,e)
# #         azel_tmp = prl.Arr1Ddouble(2)
# #         prl.satazel(pos,e,azel_tmp)
# #         azel[i*2] = azel_tmp[0]
# #         azel[i*2+1] = azel_tmp[1]

# #         if azel_tmp[1] < 0:
# #             ex.append(i)
# #             continue
        

# #         prl.ionocorr(time,nav,sats[i],pos,azel_tmp,prl.IONOOPT_BRDC,dion,vion)
# #         prl.tropcorr(time,nav,pos,azel_tmp,prl.TROPOPT_SAAS,dtrp,vtrp)
# #         vions.append(vion.ptr)
# #         vtrps.append(vtrp.ptr)
# #         prl.satno2id(sats[i],sysname)
# #         try:
# #             los = nlos[sysname.ptr]
# #         except:
# #             los = 0
# #         if los:
# #             vel = 0.0001
# #         else:
# #             vel = varerr(5*prl.D2R,sysname.ptr[0])
# #         vels.append(vel)
# #         if 'G' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,1,0,0,0])
# #             Rt.append(r+rp[3]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['G']+=1
# #         elif 'C' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,0,1,0,0])
# #             Rt.append(r+rp[4]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['C']+=1
# #         elif 'E' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,0,0,1,0])
# #             Rt.append(r+rp[5]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['E']+=1
# #         elif 'R' in sysname.ptr:
# #             Ht.append([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r,0,0,0,1])
# #             Rt.append(r+rp[6]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #             count['R']+=1
# #     if n-len(ex) > 3:
# #         H = np.vstack(Ht).astype(np.float64)
# #         R = np.vstack(Rt).astype(np.float64)
# #     else:
# #         H = np.zeros(1)
# #         R = np.zeros(1)
# #     sysinfo = np.where(np.any(H!=0,axis=0))[0]
# #     H = H[:,sysinfo]
# #     return H,R,azel,ex,sysinfo,count,vels,vions,vtrps

# # def get_ls_pnt_pos(o, nav, sta=None, exsatids=[], fixed_pos=None):
# #     """
# #     真值辅助版 SPP (带显微镜调试)
# #     """
# #     # 1. 准备工作
# #     WAVELENGTH_L1 = prl.CLIGHT / prl.FREQ1 
# #     opt = prl.prcopt_default
# #     opt.navsys = 63  # 强制开启所有系统

# #     # 2. 计算卫星位置 (V13 证明这步已经成功了)
# #     rs, noeph, dts, var = get_sat_pos(o.data, o.n, nav) 
    
# #     # === DEBUG: 打印一次卫星位置状态 ===
# #     if not hasattr(get_ls_pnt_pos, "debug_sat_pos_once"):
# #         print(f"\n[Debug] Epoch contains {o.n} sats.")
# #         print(f"[Debug] Sats without Ephemeris (noeph): {len(noeph)} / {o.n}")
# #         if len(noeph) < o.n:
# #             # 打印一颗成功的卫星看看
# #             good_idx = list(set(range(o.n)) - set(noeph))[0]
# #             print(f"[Debug] Example Good Sat Index: {good_idx}")
# #             print(f"[Debug] Sat Pos: {rs[good_idx*6:good_idx*6+3]}")
# #         get_ls_pnt_pos.debug_sat_pos_once = True
# #     # =================================

# #     # 3. 筛选数据
# #     prs_list, sats_list, snr_list, valid_indices = [], [], [], []
    
# #     # 调试计数器
# #     fail_rcv = 0
# #     fail_eph = 0
# #     fail_zero = 0
# #     fail_prange = 0
    
# #     for i in range(o.n):
# #         d = o.data[i]
        
# #         # 检查接收机 ID
# #         if d.rcv != 1: 
# #             fail_rcv += 1
# #             continue 
            
# #         # 检查是否有星历
# #         if i in noeph: 
# #             fail_eph += 1
# #             continue

# #         # === 核心疑点：检查观测值 P[0] ===
# #         # RINEX 3 C1C 应该映射到 P[0]，如果这里是 0，说明映射失败
# #         if d.P[0] == 0: 
# #             fail_zero += 1
# #             # 只打印一次观测值详情
# #             if not hasattr(get_ls_pnt_pos, "debug_obs_zero"):
# #                 sat_id_char = prl.Arr1Dchar(4)
# #                 prl.satno2id(d.sat, sat_id_char)
# #                 print(f"\n[Debug] 发现 P[0]=0! Sat: {sat_id_char.ptr}")
# #                 print(f"   - P array: {[d.P[k] for k in range(3)]}")
# #                 print(f"   - L array: {[d.L[k] for k in range(3)]}")
# #                 print(f"   - Code array: {[d.code[k] for k in range(3)]}")
# #                 get_ls_pnt_pos.debug_obs_zero = True
# #             continue

# #         vmeas = prl.Arr1Ddouble(1)
# #         pii = prange(d, nav, opt, vmeas) 
        
# #         if pii == 0: 
# #             fail_prange += 1
# #             continue

# #         prs_list.append(pii)
# #         sats_list.append(d.sat)
# #         snr_list.append(d.SNR[0]/1e3)
# #         valid_indices.append(i)

# #     # === DEBUG: 打印筛选结果 ===
# #     if len(prs_list) < 4 and not hasattr(get_ls_pnt_pos, "debug_filter_stats"):
# #         print(f"\n[Debug Filter] Total: {o.n}")
# #         print(f"   - Fail Rcv != 1 : {fail_rcv}")
# #         print(f"   - Fail No Eph   : {fail_eph}")
# #         print(f"   - Fail P[0]==0  : {fail_zero} (观测值为空)")
# #         print(f"   - Fail Prange=0 : {fail_prange} (计算修正失败)")
# #         print(f"   - Valid         : {len(prs_list)}")
# #         get_ls_pnt_pos.debug_filter_stats = True
# #     # ==========================

# #     if len(prs_list) < 4:
# #         return {"status":False, "msg":f"not enough sats (n={len(prs_list)})", "data":{}}

# #     # === 分支：如果有真值，直接计算特征 (必胜模式) ===
# #     if fixed_pos is not None:
# #         p = np.array(fixed_pos) 
        
# #         res = []
# #         azel = []
        
# #         # 1. 估算接收机钟差
# #         temp_biases = []
# #         for k, original_idx in enumerate(valid_indices):
# #             idx_start = original_idx * 6
# #             sat_p = np.array(rs[idx_start : idx_start + 3])
# #             sat_clk = dts[original_idx] * prl.CLIGHT
# #             r = np.linalg.norm(sat_p - p[:3])
# #             if r > 0: temp_biases.append(prs_list[k] - (r - sat_clk))
            
# #         if not temp_biases: return {"status":False, "msg":"calc bias failed"}
# #         clk_bias_est = np.median(temp_biases)

# #         # 2. 精确计算残差和角度
# #         for k, original_idx in enumerate(valid_indices):
# #             idx_start = original_idx * 6
# #             sat_p = np.array(rs[idx_start : idx_start + 3])
# #             sat_clk = dts[original_idx] * prl.CLIGHT
            
# #             r = np.linalg.norm(sat_p - p[:3])
# #             r_pred = r + clk_bias_est - sat_clk
# #             res.append(prs_list[k] - r_pred)
            
# #             r_lat, r_lon, r_alt = p3d.ecef2geodetic(p[0], p[1], p[2])
# #             enu = p3d.ecef2enu(sat_p[0], sat_p[1], sat_p[2], r_lat, r_lon, r_alt)
# #             az = np.arctan2(enu[0], enu[1])
# #             el = np.arctan2(enu[2], np.sqrt(enu[0]**2 + enu[1]**2))
# #             azel.append([az, el])

# #         return {
# #             "status": True, 
# #             "pos": np.append(p[:3], clk_bias_est), 
# #             "msg": "success (GT assisted)", 
# #             "data": {
# #                 "SNR": np.array(snr_list),
# #                 "azel": np.array(azel),
# #                 "residual": np.array(res),
# #                 "sats": np.array(sats_list),
# #                 "exclude": []
# #             }
# #         }

# #     return {"status":False, "msg":"WLS fallback disabled", "data":{}}

# #     def H_matrix_prl_torch(satpos,rp,dts,time,nav,sats,exclude = []):
# #         rp_clone = rp.clone().detach().cpu().numpy()
# #         ex = [] # exclude sat order
# #         n = int(len(satpos)/6)
# #         Ht = []
# #         Rt = []
# #         e = prl.Arr1Ddouble(3)
# #         rr = prl.Arr1Ddouble(3)
# #         rr[0] = rp_clone[0]
# #         rr[1] = rp_clone[1]
# #         rr[2] = rp_clone[2]
# #         azel = prl.Arr1Ddouble(n*2)
# #         pos = prl.Arr1Ddouble(3)
# #         prl.ecef2pos(rr,pos)
        
# #         dion = prl.Arr1Ddouble(1)
# #         vion = prl.Arr1Ddouble(1)
# #         dtrp = prl.Arr1Ddouble(1)
# #         vtrp = prl.Arr1Ddouble(1)

# #         vels = []
# #         vions = []
# #         vtrps = []

# #         sysname = prl.Arr1Dchar(4)
# #         count = {'G':0,'C':0,'E':0,'R':0}
# #         for i in range(n):
# #             if i in exclude:
# #                 ex.append(i)
# #                 continue
# #             sp = np.array(satpos[i*6+0:i*6+3])
# #             sp = torch.tensor(sp,dtype=torch.float64).to('cuda')
# #             #r = np.linalg.norm(sp-rp[:3])
# #             #r = prl.geodist(satpos[i*6:i*6+3],rr,e)
# #             r = torch.norm(sp-rp[:3])+prl.OMGE*(sp[0]*rp[1]-sp[1]*rp[0])/prl.CLIGHT
# #             azel_tmp = prl.Arr1Ddouble(2)
# #             prl.satazel(pos,e,azel_tmp)
# #             azel[i*2] = azel_tmp[0]
# #             azel[i*2+1] = azel_tmp[1]

# #             if azel_tmp[1] < 0:
# #                 ex.append(i)
# #                 continue
# #             prl.ionocorr(time,nav,sats[i],pos,azel_tmp,prl.IONOOPT_BRDC,dion,vion)
# #             prl.tropcorr(time,nav,pos,azel_tmp,prl.TROPOPT_SAAS,dtrp,vtrp)
# #             vions.append(vion.ptr)
# #             vtrps.append(vtrp.ptr)
# #             prl.satno2id(sats[i],sysname)
# #             vel = varerr(azel_tmp[1],sysname.ptr[0])
# #             vels.append(vel)
# #             if 'G' in sysname.ptr:
# #                 Ht.append(torch.hstack([torch.hstack([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r]),torch.tensor([1,0,0,0],dtype=torch.float64).to('cuda')]))
# #                 Rt.append(r+rp[3]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #                 count['G']+=1
# #             elif 'C' in sysname.ptr:
# #                 Ht.append(torch.hstack([torch.hstack([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r]),torch.tensor([0,1,0,0],dtype=torch.float64).to('cuda')]))
# #                 Rt.append(r+rp[4]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #                 count['C']+=1
# #             elif 'E' in sysname.ptr:
# #                 Ht.append(torch.hstack([torch.hstack([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r]),torch.tensor([0,0,1,0],dtype=torch.float64).to('cuda')]))
# #                 Rt.append(r+rp[5]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #                 count['E']+=1
# #             elif 'R' in sysname.ptr:
# #                 Ht.append(torch.hstack([torch.hstack([-(sp[0]-rp[0])/r,-(sp[1]-rp[1])/r,-(sp[2]-rp[2])/r]),torch.tensor([0,0,0,1],dtype=torch.float64).to('cuda')]))
# #                 Rt.append(r+rp[6]-prl.CLIGHT*dts[i*2]+dtrp.ptr+dion.ptr)
# #                 count['R']+=1
# #         if n-len(ex) > 3:
# #             H = torch.vstack(Ht)
# #             R = torch.vstack(Rt)
# #         else:
# #             H = torch.zeros((1,7))
# #             R = torch.zeros((1,1))
# #             #return H,R,azel,ex,np.array([]),count,vels,vions,vtrps
# #         sysinfo = np.where(np.any(H.detach().cpu().numpy()!=0,axis=0))[0]
# #         H = H[:,sysinfo]
# #         return H,R,azel,ex,sysinfo,count,vels,vions,vtrps

# #     def get_ls_pnt_pos_torch(o,nav,w = None, b = None, p_init = None, exsatids=[]):
# #         maxiter = 10
# #         if o.n < 4:
# #             return {"status":False,"pos":torch.tensor([0,0,0,0],dtype=torch.float32),"msg":"no enough observations","data":{}}
# #         rs,noeph,dts,var = get_sat_pos(o.data,o.n,nav)
# #         # if noeph :
# #         #     print('some sats without ephemeris')
# #         prs = []
# #         SNR = []
# #         exclude = []
# #         sats = []
# #         opt = prl.prcopt_default
# #         skip = 0
# #         sysname = prl.Arr1Dchar(4)
# #         vmeas = prl.Arr1Ddouble(1)
# #         for ii in range(o.n):
# #             if ii in noeph:
# #                 skip+=1
# #                 continue
# #             obsd = o.data[ii]
# #             pii = obsd.P[0] #only process L1
# #             prl.satno2id(obsd.sat,sysname)
# #             if  pii == 0 or obsd.sat in exsatids or sysname.ptr[0] not in ['G','C','R','E']:
# #                 exclude.append(ii-skip)
# #                 prs.append(0)
# #                 SNR.append(0)
# #                 sats.append(obsd.sat)
# #                 continue
# #             pii = prange(obsd,nav,opt,vmeas)
# #             prs.append(pii)
# #             sats.append(obsd.sat)
# #             SNR.append(obsd.SNR[0]/1e3)
# #             var[ii-skip] += vmeas.ptr
# #         prs = np.vstack(prs)
# #         SNR = np.array(SNR)
# #         if p_init is None:
# #             p = torch.tensor([0,0,0,0,0,0,0],dtype=torch.float64).to('cuda')
# #         else:
# #             p = torch.tensor(p_init,dtype=torch.float64).to('cuda')
# #         dp = torch.tensor([100,100,100],dtype=torch.float64)
# #         iii = 0 
# #         while torch.norm(dp)>0.0001 and iii < maxiter:
# #             #H,R,azel,ex,sysinfo,syscount,vels,vions,vtrps = H_matrix_prl(rs,p.clone().detach().cpu().numpy(),dts,o.data[0].time,nav,sats,exclude)
# #             H,R,azel,ex,sysinfo,syscount,vels,vions,vtrps = H_matrix_prl_torch(rs,p,dts,o.data[0].time,nav,sats,exclude)
# #             inc = set(range(o.n-len(noeph)))-set(ex)
# #             if len(inc) < 4:
# #                 iii+=1
# #                 continue
# #             resd = torch.tensor(prs[list(inc)],dtype=torch.float64).to('cuda') - R
# #             #resd = prs[list(inc)] - R
# #             #H = torch.tensor(H,dtype=torch.float64).to('cuda')
# #             #resd = torch.tensor(resd,dtype=torch.float64).to('cuda')
# #             if w is None:
# #                 w = torch.eye(H.shape[0],dtype=torch.float64).to('cuda')
# #             if b is None:
# #                 b = torch.zeros_like(resd)
# #             dp = wls_solve_torch(H,resd,w,b)
# #             p[sysinfo] = p[sysinfo]+dp.squeeze()
# #             # if unroll:
# #             #     p[sysinfo] = p[sysinfo]+dp.squeeze()
# #             # else:
# #             # p_init_detch = p[sysinfo].detach()
# #             # p[sysinfo] = p_init_detch+dp.squeeze()
# #             iii+=1
# #         if iii >= 10:
# #             return {"status":False,"pos":p,"msg":"over max iteration times","data":{"residual":resd}}
# #         resd = resd.detach().cpu().numpy()
# #         if np.sqrt((resd*resd).sum()) > 1000:
# #             return {"status":False,"pos":p,"msg":"residual too large","data":{"residual":resd}}
# #         H,R,azel,ex,sysinfo,syscount,vels,vions,vtrps = H_matrix_prl(rs,p.detach().cpu().numpy(),dts,o.data[0].time,nav,sats,exclude)
# #         return {"status":True,"pos":p,"msg":"success","data":{"residual":resd,'azel':azel,"exclude":ex,"eph":rs,'dts':dts,'sats':sats,'prs':prs[list(inc)],'SNR':SNR[list(inc)]}}
    
# # def goGPSw(S,el):
# #     A = 30
# #     a = 20
# #     s_0 = 10
# #     s_1 = 50
# #     def k1(s):
# #         return -(s - s_1) / a

# #     def k2(s):
# #         return (s - s_1) / (s_0 - s_1)

# #     def w(S, theta):
# #         if S < s_1:
# #             return (1 / np.sin(theta)**2) * (10**k1(S) * ((A / 10**k1(s_0) - 1) * k2(S) + 1))
# #         else:
# #             return 1
# #     return w(S,el)

# # def goGPSW(in_data):
# #     ret = []
# #     for i in in_data:
# #         ret.append(1/goGPSw(i[0],i[1]))
# #     ret = np.array(ret)
# #     return ret

# # # ==========================================
# # # 请将以下代码覆盖 rtk_util.py 末尾的对应函数
# # # ==========================================

# # def load_imu_data(imu_csv_path):
# #     """
# #     读取 IMU CSV 文件 (自动适配 InGVIO/bagpy 和 UrbanNav 格式)
# #     """
# #     print(f"Loading IMU data from {imu_csv_path}...")
# #     try:
# #         df = pd.read_csv(imu_csv_path)
        
# #         # 1. 统一时间列名
# #         if 'Time' in df.columns:
# #             df.rename(columns={'Time': 'timestamp'}, inplace=True)
# #         elif 'timestamp' not in df.columns and len(df.columns) > 0:
# #             # 如果没有标准头，默认第一列是时间
# #             df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)
            
# #         # 2. 提取数据
# #         new_df = pd.DataFrame()
# #         new_df['timestamp'] = df['timestamp']
        
# #         # 情况A: InGVIO / bagpy 格式 (angular_velocity.x ...)
# #         if 'angular_velocity.x' in df.columns:
# #             new_df['gx'] = df['angular_velocity.x']
# #             new_df['gy'] = df['angular_velocity.y']
# #             new_df['gz'] = df['angular_velocity.z']
# #             new_df['ax'] = df['linear_acceleration.x']
# #             new_df['ay'] = df['linear_acceleration.y']
# #             new_df['az'] = df['linear_acceleration.z']
            
# #         # 情况B: UrbanNav 格式 (omega_x, alpha_x ...)
# #         elif 'omega_x' in df.columns:
# #             new_df['gx'] = df['omega_x']
# #             new_df['gy'] = df['omega_y']
# #             new_df['gz'] = df['omega_z']
# #             new_df['ax'] = df['alpha_x']
# #             new_df['ay'] = df['alpha_y']
# #             new_df['az'] = df['alpha_z']
            
# #         # 情况C: 通用简写 (gx, ax ...)
# #         elif 'gx' in df.columns:
# #              new_df = df[['timestamp', 'gx', 'gy', 'gz', 'ax', 'ay', 'az']]
             
# #         else:
# #             print(f"Error: Unknown IMU columns: {df.columns}")
# #             return None

# #         # 排序
# #         new_df = new_df.sort_values(by='timestamp').reset_index(drop=True)
        
# #         # 检查时间单位，如果是纳秒(19位)，转为秒
# #         if new_df['timestamp'].iloc[0] > 1e18: # 纳秒
# #             new_df['timestamp'] = new_df['timestamp'] / 1e9
# #         elif new_df['timestamp'].iloc[0] > 1e12: # 毫秒
# #              new_df['timestamp'] = new_df['timestamp'] / 1e3
             
# #         return new_df
        
# #     except Exception as e:
# #         print(f"Error loading IMU data: {e}")
# #         return None

# # def get_imu_features(imu_df, current_time, window=1.0):
# #     """ 获取当前时间窗口内的 IMU 特征 """
# #     t_start = current_time - (window / 2)
# #     t_end = current_time + (window / 2)
# #     mask = (imu_df['timestamp'] >= t_start) & (imu_df['timestamp'] <= t_end)
# #     subset = imu_df.loc[mask]
# #     if len(subset) < 1: return np.zeros(6)
# #     # 取后6列均值
# #     return subset.iloc[:, 1:].mean().values

# # def get_spp_features(o, nav):
# #     """
# #     单点定位(SPP)特征提取 - 强壮版
# #     """
# #     try:
# #         # 这里最容易报错
# #         ret = get_wls_pnt_pos(o, nav)
# #     except Exception as e:
# #         # 只要报错，不管是 numpy 还是 math，全部捕获，返回失败即可
# #         return {"status": False, "msg": f"Crash: {str(e)}"}
    
# #     if not ret['status']:
# #         return ret
    
# #     # 手动提取 SNR, Doppler, Residual
# #     opt = prl.prcopt_default
# #     vmeas = prl.Arr1Ddouble(1)
    
# #     _snr, _dopp, _resd, _azel, _sats = [], [], [], [], []
# #     p = ret['pos'] # 接收机位置
    
# #     # 重新计算每颗卫星的残差
# #     rs, noeph, dts, var = get_sat_pos(o.data, o.n, nav)
    
# #     for i in range(o.n):
# #         obsd = o.data[i]
# #         if i in noeph or obsd.P[0] == 0: continue
        
# #         sat_pos = np.array(rs[i*6 : i*6+3])
# #         sat_clk = dts[i*2] * prl.CLIGHT
# #         r = np.linalg.norm(sat_pos - p[:3])
# #         if r == 0: continue
        
# #         P_corr = prange(obsd, nav, opt, vmeas)
# #         if P_corr == 0: continue
        
# #         predicted_P = r + p[3] - sat_clk
# #         residual = P_corr - predicted_P
        
# #         if abs(residual) > 5000: continue # 过滤大残差
        
# #         # 计算 Az/El
# #         if np.linalg.norm(p[:3]) > 0:
# #             r_lat, r_lon, r_alt = p3d.ecef2geodetic(p[0], p[1], p[2])
# #             enu = p3d.ecef2enu(sat_pos[0], sat_pos[1], sat_pos[2], r_lat, r_lon, r_alt)
# #             az = np.arctan2(enu[0], enu[1])
# #             el = np.arctan2(enu[2], np.sqrt(enu[0]**2 + enu[1]**2))
# #         else:
# #             az, el = 0, 0
            
# #         _snr.append(obsd.SNR[0] / 1000.0) # 归一化
# #         _dopp.append(obsd.D[0])
# #         _resd.append(residual)
# #         _azel.append([az, el])
# #         _sats.append(obsd.sat)

# #     if len(_snr) < 4:
# #         return {"status": False, "msg": "not enough sats"}

# #     return {
# #         "status": True,
# #         "pos": p,
# #         "data": {
# #             "SNR": np.array(_snr),
# #             "doppler": np.array(_dopp),
# #             "residual": np.array(_resd),
# #             "azel": np.array(_azel),
# #             "sats": np.array(_sats)
# #         }
# #     }

# # def load_imu_data(imu_csv_path):
# #     """
# #     读取 bagpy 提取的 IMU CSV 文件
# #     格式: header.stamp.secs, header.stamp.nsecs, angular_velocity.x...
# #     """
# #     print(f"Loading IMU data from {imu_csv_path}...")
# #     try:
# #         df = pd.read_csv(imu_csv_path)
        
# #         # 1. 合成时间戳 (秒 + 纳秒)
# #         # bagpy 的列名通常是 header.stamp.secs 和 header.stamp.nsecs
# #         if 'header.stamp.secs' in df.columns:
# #             df['timestamp'] = df['header.stamp.secs'] + df['header.stamp.nsecs'] * 1e-9
# #         elif 'Time' in df.columns:
# #             df['timestamp'] = df['Time']
# #         else:
# #             print(f"Error: 找不到时间列! 列名: {df.columns}")
# #             return None

# #         # 2. 提取并重命名数据列
# #         # 我们需要: ax, ay, az (加速度), gx, gy, gz (角速度)
# #         # bagpy 列名通常是 linear_acceleration.x 等
# #         new_df = pd.DataFrame()
# #         new_df['timestamp'] = df['timestamp']
        
# #         new_df['ax'] = df['linear_acceleration.x']
# #         new_df['ay'] = df['linear_acceleration.y']
# #         new_df['az'] = df['linear_acceleration.z']
        
# #         new_df['gx'] = df['angular_velocity.x']
# #         new_df['gy'] = df['angular_velocity.y']
# #         new_df['gz'] = df['angular_velocity.z']

# #         # 按时间排序
# #         new_df = new_df.sort_values(by='timestamp').reset_index(drop=True)
# #         return new_df
        
# #     except Exception as e:
# #         print(f"Error loading IMU data: {e}")
# #         return None

# # def get_imu_features(imu_df, current_time, window=1.0):
# #     """
# #     获取当前 GNSS 时间点前后 window 秒内的 IMU 特征
# #     返回: [ax_mean, ay_mean, az_mean, gx_mean, gy_mean, gz_mean, acc_std, gyro_std] (8维)
# #     """
# #     if imu_df is None: 
# #         return np.zeros(8)

# #     t_start = current_time - (window / 2.0)
# #     t_end = current_time + (window / 2.0)
    
# #     # 截取窗口内数据
# #     mask = (imu_df['timestamp'] >= t_start) & (imu_df['timestamp'] <= t_end)
# #     subset = imu_df.loc[mask]
    
# #     if len(subset) < 2:
# #         return np.zeros(8) # 数据不足返回0
    
# #     # 计算统计特征
# #     # 均值 (6维)
# #     means = subset[['ax', 'ay', 'az', 'gx', 'gy', 'gz']].mean().values
    
# #     # 标准差 (2维，反映剧烈程度)
# #     acc_std = np.sqrt(subset['ax'].var() + subset['ay'].var() + subset['az'].var())
# #     gyro_std = np.sqrt(subset['gx'].var() + subset['gy'].var() + subset['gz'].var())
    
# #     return np.hstack([means, [acc_std, gyro_std]])

# # # ==========================================
# # # === 覆盖更新：带地球半径检查的推理函数 ===
# # # ==========================================

# # def check_position_validity(p):
# #     """
# #     检查解算位置是否合理
# #     地球半径约 6371km (6.371e6 m)
# #     我们允许的高度范围：-1000m 到 +50000m (涵盖潜艇到飞机)
# #     放松一点：6.3e6 到 6.5e6 之间
# #     """
# #     if p is None: return False
# #     r = np.linalg.norm(p[:3])
# #     # 如果半径小于 6000km 或大于 7000km，肯定是算飞了
# #     if r < 6.0e6 or r > 7.0e6:
# #         return False
# #     # 检查是否包含 NaN
# #     if np.isnan(p).any():
# #         return False
# #     return True

# # def robust_wls_pnt_pos(o, nav):
# #     """
# #     [推理专用] 标准 WLS (带防爆检查)
# #     """
# #     WAVELENGTH_L1 = prl.CLIGHT / prl.FREQ1 
# #     opt = prl.prcopt_default
# #     opt.navsys = 63 

# #     rs, noeph, dts, var = get_sat_pos(o.data, o.n, nav)
    
# #     prs_list, sats_list, snr_list, valid_indices = [], [], [], []
    
# #     for i in range(o.n):
# #         d = o.data[i]
# #         if d.rcv != 1 or i in noeph or d.P[0] == 0: continue
# #         vmeas = prl.Arr1Ddouble(1)
# #         pii = prange(d, nav, opt, vmeas)
# #         if pii == 0: continue
# #         prs_list.append(pii)
# #         sats_list.append(d.sat)
# #         snr_list.append(d.SNR[0]/1e3)
# #         valid_indices.append(i)

# #     if len(prs_list) < 4: return {"status":False, "msg":"not enough sats"}

# #     # 初始化：尝试用伪距加权平均作为初值，而不是 (0,0,0)
# #     # 这里简单起见还是用 (0,0,0)，依靠下面的 check 来过滤
# #     p = np.array([0,0,0,0], dtype=np.float64)
# #     final_res, final_azel = [], []
    
# #     for iter_idx in range(10): 
# #         H, res, azel = [], [], []
# #         for k, idx in enumerate(valid_indices):
# #             idx_start = idx * 6
# #             sat_p = np.array(rs[idx_start:idx_start+3])
# #             sat_clk = dts[idx] * prl.CLIGHT
# #             r = np.linalg.norm(sat_p - p[:3])
            
# #             # 防止除零
# #             if r == 0: 
# #                 # 第一次迭代如果 p=0，r就是卫星距地心距离
# #                 r = np.linalg.norm(sat_p) 
            
# #             e = (sat_p - p[:3]) / r
# #             r_pred = r + p[3] - sat_clk
# #             H.append([-e[0], -e[1], -e[2], 1])
# #             res.append(prs_list[k] - r_pred)
            
# #             # Az/El
# #             if np.linalg.norm(p[:3]) > 6.0e6: # 只有位置合理才算角度
# #                 r_lat, r_lon, r_alt = p3d.ecef2geodetic(p[0],p[1],p[2])
# #                 enu = p3d.ecef2enu(sat_p[0],sat_p[1],sat_p[2],r_lat,r_lon,r_alt)
# #                 az = np.arctan2(enu[0],enu[1])
# #                 el = np.arctan2(enu[2],np.sqrt(enu[0]**2+enu[1]**2))
# #             else: az, el = 0, 0
# #             azel.append([az, el])
            
# #         if len(res) < 4: break
# #         H = np.array(H); res = np.array(res)
# #         try:
# #             dx = np.linalg.inv(H.T @ H) @ H.T @ res
# #             p[:4] += dx
# #             if np.linalg.norm(dx) < 1e-3: break
# #         except: break
# #         final_res = res; final_azel = azel

# #     # === 关键修改：结果检查 ===
# #     if not check_position_validity(p):
# #         return {"status":False, "msg":"WLS result exploded"}

# #     return {
# #         "status": True, "pos": p,
# #         "data": {
# #             "SNR": np.array(snr_list),
# #             "azel": np.array(final_azel),
# #             "residual": np.array(final_res),
# #             "sats": np.array(sats_list)
# #         }
# #     }

# # def weighted_wls_pnt_pos(o, nav, weights, p_init=None):
# #     """
# #     [推理专用] 加权 WLS (带防爆检查)
# #     """
# #     WAVELENGTH_L1 = prl.CLIGHT / prl.FREQ1 
# #     opt = prl.prcopt_default
# #     opt.navsys = 63

# #     rs, noeph, dts, var = get_sat_pos(o.data, o.n, nav)
    
# #     prs_list, valid_indices, valid_weights = [], [], []
# #     weight_dict = {sat: w for sat, w in zip(weights['sats'], weights['values'])}
    
# #     for i in range(o.n):
# #         d = o.data[i]
# #         if d.rcv != 1 or i in noeph or d.P[0] == 0: continue
# #         if d.sat not in weight_dict: continue 
# #         vmeas = prl.Arr1Ddouble(1)
# #         pii = prange(d, nav, opt, vmeas)
# #         if pii == 0: continue
# #         prs_list.append(pii)
# #         valid_indices.append(i)
# #         valid_weights.append(weight_dict[d.sat])

# #     if len(prs_list) < 4: return {"status":False, "msg":"not enough weighted sats"}
    
# #     W_diag = np.array(valid_weights)
# #     W_diag = W_diag / (W_diag.sum() + 1e-9) * len(W_diag)
# #     W = np.diag(W_diag)

# #     if p_init is not None:
# #         p = np.array(p_init, dtype=np.float64)
# #     else:
# #         p = np.array([0,0,0,0], dtype=np.float64)
    
# #     for _ in range(10):
# #         H, res = [], []
# #         for k, idx in enumerate(valid_indices):
# #             idx_start = idx * 6
# #             sat_p = np.array(rs[idx_start:idx_start+3])
# #             sat_clk = dts[idx] * prl.CLIGHT
# #             r = np.linalg.norm(sat_p - p[:3])
# #             if r == 0: r = np.linalg.norm(sat_p) # Prevent div0
# #             e = (sat_p - p[:3]) / r
# #             r_pred = r + p[3] - sat_clk
# #             H.append([-e[0], -e[1], -e[2], 1])
# #             res.append(prs_list[k] - r_pred)
            
# #         if len(res) < 4: break
# #         H = np.array(H); res = np.array(res)
        
# #         try:
# #             H_T_W = H.T @ W
# #             matrix = H_T_W @ H + np.eye(4) * 1e-6
# #             dx = np.linalg.inv(matrix) @ H_T_W @ res
# #             p[:4] += dx
# #             if np.linalg.norm(dx) < 1e-4: break
# #         except: return {"status":False, "msg":"weighted matrix inversion failed"}

# #     # === 关键修改：结果检查 ===
# #     if not check_position_validity(p):
# #         return {"status":False, "msg":"Weighted WLS result exploded"}

# #     return {"status":True, "pos":p}

# # def wls_solve_torch(H, z, w=None, b=None):
# #     """
# #     PyTorch 版本的加权最小二乘求解器 (带正则化防奇异)
# #     """
# #     if w is None:
# #         w = torch.eye(H.shape[0], device=H.device, dtype=H.dtype)
# #     if b is None:
# #         b = torch.zeros_like(z)
    
# #     # 公式: (H^T W H + lambda*I)^-1 H^T W (z - b)
    
# #     # 1. 加上微小的正则化项 lambda，防止矩阵奇异 (Singular Matrix)
# #     lambda_reg = 1e-4 
# #     I = torch.eye(H.shape[1], device=H.device, dtype=H.dtype) * lambda_reg
    
# #     # 2. 构建正规方程
# #     # A = H^T W H + I
# #     A = H.t() @ w @ H + I
# #     # B = H^T W (z - b)
# #     B = H.t() @ w @ (z - b)
    
# #     try:
# #         # 3. 求解 dx
# #         x = torch.linalg.solve(A, B)
# #         return x
# #     except Exception as e:
# #         # 如果还是炸了，返回 0 梯度
# #         return torch.zeros((H.shape[1], 1), device=H.device, dtype=H.dtype)
    
# # def get_ls_pnt_pos_torch(o, nav, w=None, b=None, p_init=None, exsatids=[], device='cuda'):
# #     try:
# #         # 1. 获取卫星位置 (会调用上面修改过的 get_sat_pos)
# #         rs, noeph, dts, var = get_sat_pos(o.data, o.n, nav)
        
# #         sat_pos_list = []
# #         pr_list = []
# #         dts_list = []
        
# #         opt = prl.prcopt_default
# #         vmeas = prl.Arr1Ddouble(1)
        
# #         for i in range(o.n):
# #             if i in noeph: continue
# #             d = o.data[i]
            
# #             # === 新增：过滤无效伪距 ===
# #             if d.P[0] < 1000.0 or d.sat in exsatids: continue 
            
# #             try: pii = prange(d, nav, opt, vmeas)
# #             except: pii = 0
# #             if pii == 0: continue
            
# #             idx_start = i * 6
# #             sat_pos_list.append([rs[idx_start], rs[idx_start+1], rs[idx_start+2]])
# #             pr_list.append(pii)
# #             dts_list.append(dts[i*2])

# #         if len(pr_list) < 4:
# #             return {"status": False, "pos": None, "msg": "not enough valid sats"}

# #         # 2. 转 Tensor
# #         sat_pos_t = torch.tensor(sat_pos_list, dtype=torch.float64, device=device)
# #         pr_t = torch.tensor(pr_list, dtype=torch.float64, device=device)
# #         sat_clk_t = torch.tensor(dts_list, dtype=torch.float64, device=device) * prl.CLIGHT
# #         n_sat = len(pr_list)

# #         # 3. 权重处理
# #         if w is None:
# #              W_mat = torch.eye(n_sat, dtype=torch.float64, device=device)
# #         else:
# #              # 简单处理，假设 w 维度对齐
# #              if w.dim() == 1 and w.shape[0] >= n_sat:
# #                  W_mat = torch.diag(w[:n_sat].to(dtype=torch.float64))
# #              else:
# #                  W_mat = torch.eye(n_sat, dtype=torch.float64, device=device)

# #         if b is None:
# #             bias_t = torch.zeros(n_sat, dtype=torch.float64, device=device)
# #         else:
# #             bias_t = b.to(dtype=torch.float64)
# #             if bias_t.shape[0] > n_sat: bias_t = bias_t[:n_sat]

# #         # 4. 初始化
# #         x = torch.zeros(4, dtype=torch.float64, device=device)
# #         if p_init is not None:
# #              x[:3] = p_init[:3].to(device, dtype=torch.float64)
# #         else:
# #              # === 核心修复：冷启动初始化 ===
# #              # 1. 计算卫星重心的方向向量
# #              mean_sat = torch.mean(sat_pos_t, dim=0)
# #              # 2. 归一化并投影到地球表面 (半径 6371km)
# #              # 这样初始位置就在地面，而不是在太空，收敛更快更准
# #              x[:3] = (mean_sat / torch.norm(mean_sat)) * 6371000.0
             
# #         # 初始化钟差
# #         with torch.no_grad():
# #              dist_init = torch.norm(sat_pos_t - x[:3], dim=1)
# #              clk_est = pr_t - dist_init + sat_clk_t
# #              x[3] = torch.median(clk_est)

# #         # 5. 迭代求解 (Gauss-Newton)
# #         for i in range(10): 
# #             user_pos = x[:3]
# #             user_clk = x[3]
            
# #             diff = sat_pos_t - user_pos 
# #             geom_range = torch.norm(diff, dim=1) 
# #             y = pr_t - geom_range - user_clk + sat_clk_t - bias_t
            
# #             unit_vec = diff / (geom_range.unsqueeze(1) + 1e-9)
# #             H = torch.cat([-unit_vec, torch.ones((n_sat, 1), device=device, dtype=torch.float64)], dim=1) 
            
# #             lambda_reg = 1e-3 * torch.eye(4, device=device, dtype=torch.float64)
            
# #             try:
# #                 H_t_W = H.t() @ W_mat
# #                 dx = torch.linalg.solve(H_t_W @ H + lambda_reg, H_t_W @ y)
# #             except: break
            
# #             # 步长限制
# #             step = torch.norm(dx[:3])
# #             if step > 100000: dx[:3] *= (100000 / step)
            
# #             x += dx
# #             if torch.norm(dx) < 1e-4: break
            
# #         # 6. 最终检查
# #         # 确保结果在地球表面附近 (6000km - 7000km)
# #         final_r = torch.norm(x[:3])
# #         if final_r < 6000000 or final_r > 7000000:
# #              return {"status": False, "pos": None, "msg": "result out of earth"}
             
# #         return {"status": True, "pos": x, "msg": "success"}

# #     except Exception as e:
# #         return {"status": False, "pos": None, "msg": str(e)}

# import pyrtklib as prl
# import numpy as np
# import pymap3d as p3d
# import pandas as pd
# import math
# import os

# try:
#     import torch
#     torch_enable = True
# except:
#     torch_enable = False    

# SYS = {'G':prl.SYS_GPS,'C':prl.SYS_CMP,'E':prl.SYS_GAL,'R':prl.SYS_GLO,'J':prl.SYS_QZS}

# # ==========================================
# # 核心工具函数
# # ==========================================

# def enable_multi_gnss(opt_or_nav):
#     SYS_ALL = 0x01 | 0x04 | 0x08 | 0x20 # GPS|GLO|GAL|CMP
#     try: opt_or_nav.navsys = SYS_ALL
#     except: pass

# def arr_select(arr, select, step=1):
#     obj_class = type(arr)
#     n = len(select)*step
#     arr_sel = obj_class(n)
#     for i in range(len(select)):
#         for j in range(step):
#             arr_sel[i*step+j] = arr[select[i]*step+j]
#     return arr_sel

# def gettgd(sat, nav, type):
#     sys_name = prl.Arr1Dchar(4)
#     prl.satno2id(sat,sys_name)
#     sys = SYS[sys_name.ptr[0]]
#     eph = nav.eph
#     geph = nav.geph
#     if sys == prl.SYS_GLO:
#         for i in range(nav.ng):
#             if geph[i].sat == sat: break
#         return 0.0 if i >= nav.ng else -geph[i].dtaun * prl.CLIGHT
#     else:
#         for i in range(nav.n):
#             if eph[i].sat == sat: break
#         return 0.0 if i >= nav.n else eph[i].tgd[type] * prl.CLIGHT

# def prange(obs, nav, opt, var):
#     P1, P2 = obs.P[0], obs.P[1]
#     if P1 == 0.0: return 0.0
#     sat = obs.sat
#     sys_name = prl.Arr1Dchar(4)
#     prl.satno2id(sat, sys_name)
#     sys_char = sys_name.ptr[0]
    
#     # 简单的单频处理 (L1)
#     var[0] = 0.3 ** 2
#     b1 = 0.0
    
#     if sys_char == 'G' or sys_char == 'J': # GPS/QZS
#         b1 = gettgd(sat, nav, 0)
#     elif sys_char == 'C': # BDS
#         # BDS TGD logic simplified
#         b1 = gettgd(sat, nav, 0) 
#     elif sys_char == 'E': # GAL
#         b1 = gettgd(sat, nav, 0)
#     elif sys_char == 'R': # GLO
#         gamma = (prl.FREQ1_GLO / prl.FREQ2_GLO) ** 2
#         b1 = gettgd(sat, nav, 0)
#         return P1 - b1 / (gamma - 1.0)
        
#     return P1 - b1

# def get_sat_pos(obsd, n, nav, SRC_dts=False):
#     """
#     通用卫星位置计算 (返回压缩数组，用于一般用途)
#     """
#     svh = prl.Arr1Dint(prl.MAXOBS)
#     rs = prl.Arr1Ddouble(6 * n)
#     dts = prl.Arr1Ddouble(2 * n)
#     var = prl.Arr1Ddouble(1 * n)

#     # 计算
#     prl.satposs(obsd[0].time, obsd.ptr, n, nav, 0, rs, dts, var, svh)

#     noeph = []
#     for i in range(n):
#         # 检查是否无效 (0,0,0)
#         if np.linalg.norm([rs[6*i], rs[6*i+1], rs[6*i+2]]) < 1e-1:
#             noeph.append(i)

#     mask = list(set(range(n)) - set(noeph))
#     nrs = arr_select(rs, mask, 6)
#     var = arr_select(var, mask)
#     if not SRC_dts:
#         ndts = arr_select(dts, mask, 2)
#     else:
#         ndts = dts
#     return nrs, noeph, ndts, var

# def read_obs(rcv, eph, ref=None):
#     obs = prl.obs_t()
#     nav = prl.nav_t()
#     sta = prl.sta_t()
    
#     # 读取 Rover
#     print(f"Reading Rover data: {rcv}")
#     if isinstance(rcv, list):
#         for r in rcv: prl.readrnx(r, 1, "", obs, nav, sta)
#     else:
#         prl.readrnx(rcv, 1, "", obs, nav, sta)
        
#     # 读取星历
#     if isinstance(eph, list): files = eph
#     else: files = [eph]
        
#     for f in files:
#         print(f"Loading Ephemeris file: {f}")
#         if f.lower().endswith('.sp3'):
#             print(">>> Type: SP3 (Precise Orbit)")
#             prl.readsp3(f, nav, 0)
#         elif f.lower().endswith('.clk'):
#             print(">>> Type: RINEX CLK")
#             try: prl.readrnxc(f, nav)
#             except: prl.readrnx(f, 2, "", obs, nav, sta)
#         else:
#             print(">>> Type: Broadcast Ephemeris")
#             prl.readrnx(f, 2, "", obs, nav, sta)
            
#     return obs, nav, sta

# def split_obs(obs, dt_th=0.05):
#     obss = []
#     n = obs.n
#     if n == 0: return obss
#     i = 0
#     while i < n:
#         tt = obs.data[i].time
#         j = i
#         while j < n:
#             dt = prl.timediff(obs.data[j].time, tt)
#             if abs(dt) > dt_th: break
#             j += 1
#         count = j - i
#         if count > 0:
#             tmp_obs = prl.obs_t()
#             tmp_obs.n = count
#             tmp_obs.data = prl.Arr1Dobsd_t(count)
#             for k in range(count):
#                 tmp_obs.data[k] = obs.data[i + k]
#             obss.append(tmp_obs)
#         i = j
#     return obss

# # ==========================================
# # 修复后的 SPP / IMU 函数
# # ==========================================

# def check_position_validity(p):
#     if p is None: return False
#     r = np.linalg.norm(p[:3])
#     if r < 6.0e6 or r > 7.0e6: return False # 地球半径检查
#     if np.isnan(p).any(): return False
#     return True

# def robust_wls_pnt_pos(o, nav):
#     """
#     [修复版] 鲁棒 SPP 解算
#     直接使用未压缩的 raw_rs 数组，防止索引越界 (Index Out of Bounds)
#     """
#     opt = prl.prcopt_default
#     opt.navsys = 63 

#     # 1. 直接获取 Raw Array (不通过 get_sat_pos 压缩)
#     n = o.n
#     svh = prl.Arr1Dint(prl.MAXOBS)
#     raw_rs = prl.Arr1Ddouble(6 * n) # 6 * n, 即使无效卫星也占位
#     raw_dts = prl.Arr1Ddouble(2 * n)
#     var = prl.Arr1Ddouble(1 * n)
    
#     # 计算卫星位置
#     prl.satposs(o.data[0].time, o.data.ptr, n, nav, 0, raw_rs, raw_dts, var, svh)
    
#     prs_list = []
#     sats_list = []
#     snr_list = []
#     valid_indices = []
    
#     # 2. 筛选有效卫星
#     for i in range(n):
#         d = o.data[i]
        
#         # 检查1: 接收机ID
#         if d.rcv != 1: continue
        
#         # 检查2: 卫星坐标是否为0 (无效)
#         # 注意: 这里使用 i*6 直接访问，绝对安全
#         idx_start = i * 6
#         if np.linalg.norm([raw_rs[idx_start], raw_rs[idx_start+1], raw_rs[idx_start+2]]) < 0.1:
#             continue
            
#         # 检查3: 伪距是否有效
#         if d.P[0] == 0: continue
        
#         vmeas = prl.Arr1Ddouble(1)
#         pii = prange(d, nav, opt, vmeas)
#         if pii == 0: continue
        
#         prs_list.append(pii)
#         sats_list.append(d.sat)
#         snr_list.append(d.SNR[0]/1e3)
#         valid_indices.append(i) # 记录原始索引

#     if len(prs_list) < 4: 
#         return {
#             "status": False, 
#             "pos": np.zeros(6), 
#             "msg": f"not enough sats ({len(prs_list)})",
#             "data": {}
#         }

#     # 3. WLS 迭代求解
#     p = np.array([0,0,0,0], dtype=np.float64)
#     final_res = []
    
#     # 初始化位置 (尝试用第一颗卫星推算，避免 0,0,0 导致 H 矩阵奇异)
#     if len(valid_indices) > 0:
#         idx0 = valid_indices[0]
#         p[:3] = np.array([raw_rs[idx0*6], raw_rs[idx0*6+1], raw_rs[idx0*6+2]]) * 0.9 # 地面点
        
#     for iter_idx in range(10): 
#         H = []
#         res = []
        
#         for k, idx in enumerate(valid_indices):
#             # 这里的 idx 是原始索引，对应 raw_rs 的 idx*6，完全匹配
#             idx_start = idx * 6
#             sat_p = np.array([raw_rs[idx_start], raw_rs[idx_start+1], raw_rs[idx_start+2]])
#             sat_clk = raw_dts[idx*2] * prl.CLIGHT
            
#             r = np.linalg.norm(sat_p - p[:3])
#             if r == 0: r = 1.0 # 避免除零
            
#             e = (sat_p - p[:3]) / r
#             r_pred = r + p[3] - sat_clk
            
#             # 简单的地球自转修正 (Sagnac)
#             # OMEGA_EARTH = 7.2921151467e-5
#             # sagnac = OMEGA_EARTH * (sat_p[0]*p[1] - sat_p[1]*p[0]) / prl.CLIGHT
#             # r_pred += sagnac
            
#             H.append([-e[0], -e[1], -e[2], 1.0])
#             res.append(prs_list[k] - r_pred)
            
#         if len(res) < 4: break
        
#         H_mat = np.array(H)
#         res_vec = np.array(res)
        
#         try:
#             # dx = (H^T H)^-1 H^T res
#             dx = np.linalg.inv(H_mat.T @ H_mat) @ H_mat.T @ res_vec
#             p[:4] += dx
#             if np.linalg.norm(dx) < 1e-3: break
#         except: 
#             return {"status":False, "msg":"Singular Matrix"}
            
#         final_res = res_vec

#     # 4. 结果检查
#     if not check_position_validity(p):
#         return {"status":False, "msg":"Result exploded"}

#     return {
#         "status": True, 
#         "pos": p,
#         "data": {
#             "SNR": np.array(snr_list),
#             "residual": np.array(final_res),
#             "sats": np.array(sats_list)
#         }
#     }

# def load_imu_data(imu_csv_path):
#     """
#     读取 IMU CSV (InGVIO/bagpy/UrbanNav 格式兼容)
#     """
#     print(f"Loading IMU data from {imu_csv_path}...")
#     try:
#         df = pd.read_csv(imu_csv_path)
        
#         # 1. 统一时间列
#         if 'Time' in df.columns: df.rename(columns={'Time': 'timestamp'}, inplace=True)
#         elif 'header.stamp.secs' in df.columns:
#              df['timestamp'] = df['header.stamp.secs'] + df['header.stamp.nsecs'] * 1e-9
#         elif 'timestamp' not in df.columns:
#              df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)
             
#         # 2. 提取数据 (gx,gy,gz, ax,ay,az)
#         new_df = pd.DataFrame()
#         new_df['timestamp'] = df['timestamp']
        
#         # 尝试匹配常见列名
#         col_map = {
#             'gx': ['angular_velocity.x', 'omega_x', 'gx'],
#             'gy': ['angular_velocity.y', 'omega_y', 'gy'],
#             'gz': ['angular_velocity.z', 'omega_z', 'gz'],
#             'ax': ['linear_acceleration.x', 'alpha_x', 'ax'],
#             'ay': ['linear_acceleration.y', 'alpha_y', 'ay'],
#             'az': ['linear_acceleration.z', 'alpha_z', 'az']
#         }
        
#         for target, candidates in col_map.items():
#             for c in candidates:
#                 if c in df.columns:
#                     new_df[target] = df[c]
#                     break
        
#         # 检查是否全部提取成功
#         if len(new_df.columns) < 7:
#             print(f"IMU Columns missing. Found: {new_df.columns}")
#             return None
            
#         # 排序与单位修正
#         new_df = new_df.sort_values(by='timestamp').reset_index(drop=True)
        
#         # 纳秒/毫秒检测
#         t0 = new_df['timestamp'].iloc[0]
#         if t0 > 1e18: new_df['timestamp'] /= 1e9
#         elif t0 > 1e12: new_df['timestamp'] /= 1e3
            
#         return new_df
        
#     except Exception as e:
#         print(f"Error loading IMU: {e}")
#         return None

import pyrtklib as prl
import numpy as np
import pymap3d as p3d
import pandas as pd
import math
import os

# ==========================================
# 核心工具函数
# ==========================================

def arr_select(arr, select, step=1):
    obj_class = type(arr)
    n = len(select)*step
    arr_sel = obj_class(n)
    for i in range(len(select)):
        for j in range(step):
            arr_sel[i*step+j] = arr[select[i]*step+j]
    return arr_sel

def gettgd(sat, nav, type):
    sys_name = prl.Arr1Dchar(4)
    prl.satno2id(sat,sys_name)
    sys_char = sys_name.ptr[0]
    eph = nav.eph
    geph = nav.geph
    
    if sys_char == 'R': # GLONASS
        for i in range(nav.ng):
            if geph[i].sat == sat: break
        return 0.0 if i >= nav.ng else -geph[i].dtaun * prl.CLIGHT
    else:
        for i in range(nav.n):
            if eph[i].sat == sat: break
        return 0.0 if i >= nav.n else eph[i].tgd[type] * prl.CLIGHT

def prange(obs, nav, opt, var):
    P1 = obs.P[0]
    if P1 == 0.0: return 0.0
    sat = obs.sat
    sys_name = prl.Arr1Dchar(4)
    prl.satno2id(sat, sys_name)
    sys_char = sys_name.ptr[0]
    
    # 简单的单频处理 (L1)
    var[0] = 0.3 ** 2
    b1 = 0.0
    
    if sys_char == 'G' or sys_char == 'J' or sys_char == 'E': 
        b1 = gettgd(sat, nav, 0)
    elif sys_char == 'C': # BDS
        b1 = gettgd(sat, nav, 0) 
    elif sys_char == 'R': # GLO
        gamma = (prl.FREQ1_GLO / prl.FREQ2_GLO) ** 2
        b1 = gettgd(sat, nav, 0)
        return P1 - b1 / (gamma - 1.0)
        
    return P1 - b1

def read_obs(rcv, eph, ref=None):
    obs = prl.obs_t()
    nav = prl.nav_t()
    sta = prl.sta_t()
    
    print(f"Reading Rover data: {rcv}")
    if isinstance(rcv, list):
        for r in rcv: prl.readrnx(r, 1, "", obs, nav, sta)
    else:
        prl.readrnx(rcv, 1, "", obs, nav, sta)
        
    if isinstance(eph, list): files = eph
    else: files = [eph]
        
    for f in files:
        print(f"Loading Ephemeris file: {f}")
        try:
            prl.readrnx(f, 2, "", obs, nav, sta)
        except:
            pass
            
    return obs, nav, sta

def split_obs(obs, dt_th=0.05):
    obss = []
    n = obs.n
    if n == 0: return obss
    i = 0
    while i < n:
        tt = obs.data[i].time
        j = i
        while j < n:
            dt = prl.timediff(obs.data[j].time, tt)
            if abs(dt) > dt_th: break
            j += 1
        count = j - i
        if count > 0:
            tmp_obs = prl.obs_t()
            tmp_obs.n = count
            tmp_obs.data = prl.Arr1Dobsd_t(count)
            for k in range(count):
                tmp_obs.data[k] = obs.data[i + k]
            obss.append(tmp_obs)
        i = j
    return obss

# ==========================================
# 核心解算函数 (修复版)
# ==========================================

def check_position_validity(p):
    if p is None: return False
    r = np.linalg.norm(p[:3])
    # 放宽范围: 6000km - 7000km (涵盖高空和地表)
    if r < 6.0e6 or r > 7.0e6: return False 
    if np.isnan(p).any(): return False
    return True

def robust_wls_pnt_pos(o, nav):
    """
    [修复版] 鲁棒 SPP 解算
    ✅ 包含 Sagnac 效应修正
    ✅ 包含地球自转修正
    """
    opt = prl.prcopt_default
    opt.navsys = 63 
    OMEGA_EARTH = 7.2921151467e-5
    CLIGHT = prl.CLIGHT

    n = o.n
    # 使用原始数组避免压缩带来的索引错位
    svh = prl.Arr1Dint(prl.MAXOBS)
    raw_rs = prl.Arr1Ddouble(6 * n) 
    raw_dts = prl.Arr1Ddouble(2 * n)
    var = prl.Arr1Ddouble(1 * n)
    
    # 1. 计算卫星位置
    prl.satposs(o.data[0].time, o.data.ptr, n, nav, 0, raw_rs, raw_dts, var, svh)
    
    prs_list = []
    valid_indices = []
    
    # 2. 筛选有效卫星
    for i in range(n):
        d = o.data[i]
        if d.rcv != 1: continue
        
        # 检查卫星坐标有效性
        idx_start = i * 6
        if np.linalg.norm([raw_rs[idx_start], raw_rs[idx_start+1], raw_rs[idx_start+2]]) < 1000.0:
            continue
            
        if d.P[0] == 0: continue
        
        vmeas = prl.Arr1Ddouble(1)
        pii = prange(d, nav, opt, vmeas)
        if pii == 0: continue
        
        prs_list.append(pii)
        valid_indices.append(i) 

    if len(prs_list) < 4: 
        return {"status": False, "pos": np.zeros(6), "msg": "not enough sats", "data": {}}

    # 3. WLS 迭代求解
    p = np.array([0,0,0,0], dtype=np.float64)
    
    # 初始化: 用第一颗卫星的位置稍微缩放一下作为地表初值
    if len(valid_indices) > 0:
        idx0 = valid_indices[0]
        sat0 = np.array([raw_rs[idx0*6], raw_rs[idx0*6+1], raw_rs[idx0*6+2]])
        p[:3] = sat0 / np.linalg.norm(sat0) * 6371000.0

    last_res = np.array([0.0])
        
    for iter_idx in range(10): 
        H = []
        res = []
        
        for k, idx in enumerate(valid_indices):
            idx_start = idx * 6
            sat_p = np.array([raw_rs[idx_start], raw_rs[idx_start+1], raw_rs[idx_start+2]])
            sat_clk = raw_dts[idx*2] * CLIGHT
            
            # 几何距离
            r = np.linalg.norm(sat_p - p[:3])
            if r == 0: r = 1.0
            
            # [cite_start]🔧 [修复] Sagnac 效应 (地球自转修正) [cite: 33]
            # 卫星发射信号时地球的位置 vs 接收机接收信号时地球的位置
            sagnac = OMEGA_EARTH * (sat_p[0]*p[1] - sat_p[1]*p[0]) / CLIGHT
            
            r_pred = r + p[3] - sat_clk + sagnac
            
            # 观测矢量 / 雅可比矩阵
            e = (sat_p - p[:3]) / r
            H.append([-e[0], -e[1], -e[2], 1.0])
            res.append(prs_list[k] - r_pred)
            
        if len(res) < 4: break
        
        H_mat = np.array(H)
        res_vec = np.array(res)
        last_res = res_vec
        
        try:
            dx = np.linalg.inv(H_mat.T @ H_mat) @ H_mat.T @ res_vec
            p[:4] += dx
            if np.linalg.norm(dx) < 1e-3: break
        except: 
            return {"status":False, "msg":"Singular Matrix"}

    if not check_position_validity(p):
        return {"status":False, "msg":"Result exploded"}

    # --- 新增：提取单星微观特征 ---
    snr_arr = []
    el_arr = []
    for k, idx in enumerate(valid_indices):
        d = o.data[idx]
        snr_arr.append(d.SNR[0] / 1000.0) # 归一化 SNR
        
        # 计算每颗星的高度角
        idx_start = idx * 6
        sat_p = np.array([raw_rs[idx_start], raw_rs[idx_start+1], raw_rs[idx_start+2]])
        r_lat, r_lon, r_alt = p3d.ecef2geodetic(p[0], p[1], p[2])
        enu = p3d.ecef2enu(sat_p[0], sat_p[1], sat_p[2], r_lat, r_lon, r_alt)
        el = np.arctan2(enu[2], np.sqrt(enu[0]**2 + enu[1]**2))
        el_arr.append(el)

    return {
        "status": True,
        "pos": p,
        "residuals": last_res,
        "snr": np.array(snr_arr),
        "el": np.array(el_arr)
    }

def load_imu_data(imu_csv_path):
    """
    读取 IMU CSV 并标准化输出列: [timestamp, gx, gy, gz, ax, ay, az]
    """
    print(f"Loading IMU data from {imu_csv_path}...")
    try:
        df = pd.read_csv(imu_csv_path)
        
        # 1. 统一时间列
        if 'Time' in df.columns: df.rename(columns={'Time': 'timestamp'}, inplace=True)
        elif 'header.stamp.secs' in df.columns:
             df['timestamp'] = df['header.stamp.secs'] + df['header.stamp.nsecs'] * 1e-9
        elif 'timestamp' not in df.columns:
             df.rename(columns={df.columns[0]: 'timestamp'}, inplace=True)
             
        # 2. 提取数据 (gx,gy,gz, ax,ay,az)
        new_df = pd.DataFrame()
        new_df['timestamp'] = df['timestamp']
        
        # 尝试匹配常见列名
        col_map = {
            'gx': ['angular_velocity.x', 'omega_x', 'gx', 'field.angular_velocity.x'],
            'gy': ['angular_velocity.y', 'omega_y', 'gy', 'field.angular_velocity.y'],
            'gz': ['angular_velocity.z', 'omega_z', 'gz', 'field.angular_velocity.z'],
            'ax': ['linear_acceleration.x', 'alpha_x', 'ax', 'field.linear_acceleration.x'],
            'ay': ['linear_acceleration.y', 'alpha_y', 'ay', 'field.linear_acceleration.y'],
            'az': ['linear_acceleration.z', 'alpha_z', 'az', 'field.linear_acceleration.z']
        }
        
        for target, candidates in col_map.items():
            found = False
            for c in candidates:
                if c in df.columns:
                    new_df[target] = df[c]
                    found = True
                    break
            if not found:
                # 如果找不到，尝试按列索引兜底 (假设 1-3 是 gyro, 4-6 是 acc)
                # 这非常危险，仅作为最后手段
                pass 
        
        if len(new_df.columns) < 7:
            print(f"❌ Error: IMU Columns missing. Found: {new_df.columns}")
            return None
            
        new_df = new_df.sort_values(by='timestamp').reset_index(drop=True)
        
        # 单位修正 (纳秒 -> 秒)
        t0 = new_df['timestamp'].iloc[0]
        if t0 > 1e18: new_df['timestamp'] /= 1e9
        elif t0 > 1e12: new_df['timestamp'] /= 1e3
            
        return new_df
        
    except Exception as e:
        print(f"Error loading IMU: {e}")
        return None