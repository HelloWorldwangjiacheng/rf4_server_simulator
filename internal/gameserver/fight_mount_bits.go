package gameserver

import "rf4server/internal/proto"

// 搏鱼期 4/22 挂载运行位注入。
//
// 客户端搏鱼态进入时一次性读取"钩组实例/玩法分类/作钓活跃"三个本地挂载态并
// 锁定整场；服务端搏鱼期 4/22 里挂装组件若全是定义基值裸值、拟饵树缺席，路亚
// 钩组实例构造/玩法判定翻车 → 保持力 ×0.05 → 秒脱（归因：
// docs/路亚秒脱钩归因分析-2026-11-12.md）。官方 lure2 抓包（2026-11-12，19 帧）
// 证实搏鱼期每 2s 全树帧中所有挂装组件 flags = 定义基值 | 运行位：
//
//	拟饵/钩 +1024；竿/轮/主线/前导/丝锁 +1024|2048；轮零件 +1024。
//
// 旋钮（cat34）官方观测无增量、竿子件（cat36/4/5）增量不一，都不进表 = 不注入。

// fightMountBitsByCat 搏鱼期挂载运行位增量表（cat → bits），
// 与 spec Evidence 表逐项一致；不在表内的品类不注入。
var fightMountBitsByCat = map[int64]uint64{
	3:  fightMountBitsRod, // 竿
	6:  fightMountBitsRod, // 轮
	11: fightMountBitsRod, // 主线
	13: fightMountBitsRod, // 前导
	14: fightMountBitsRod, // 丝锁
	17: hookMountedFlag,   // 拟饵
	12: hookMountedFlag,   // 钩
	7:  hookMountedFlag,   // 轮零件：线杯
	8:  hookMountedFlag,   // 轮零件：轴承
	10: hookMountedFlag,   // 轮零件：轮油
	52: hookMountedFlag,   // 轮零件：齿轮
}

const (
	// fightMountBitsRod 竿/轮/线族运行位：挂装位 + 装备就绪位（1024|2048）。
	fightMountBitsRod = uint64(1024 | 2048)
)

// collectFightNumericIDs 收集树中所有带 iofbjlaadfg 对象的数字 id，
// 供一次批量 IN 查询拿品类（push 每 2s 热路径，禁止逐对象单查）。
func collectFightNumericIDs(v *proto.Value, into map[int64]struct{}) {
	if v == nil {
		return
	}
	if v.Kind == proto.KindObj {
		if ni := fieldIdxByCS(v.Class, csNumericID); ni >= 0 && ni < len(v.Fields) &&
			v.Fields[ni].Num != nil {
			into[int64(u64Of(v.Fields[ni].Num))] = struct{}{}
		}
	}
	for _, f := range v.Fields {
		if f.Val != nil {
			collectFightNumericIDs(f.Val, into)
		}
	}
	for _, it := range v.Items {
		collectFightNumericIDs(it, into)
	}
}

// markFightMounted 递归遍历树，按每层对象的 iofbjlaadfg（定义下标）查 cat，
// 把增量表中的挂载运行位 OR 进 hgaijieklek；无 iofbj 字段的对象跳过。
// catOf 由调用方提供（批量查询结果闭包），本函数不做任何 IO。
func markFightMounted(v *proto.Value, catOf func(numericID int64) (int64, bool)) {
	if v == nil || catOf == nil {
		return
	}
	if v.Kind == proto.KindObj {
		if ni := fieldIdxByCS(v.Class, csNumericID); ni >= 0 && ni < len(v.Fields) &&
			v.Fields[ni].Num != nil {
			if cat, ok := catOf(int64(u64Of(v.Fields[ni].Num))); ok {
				if bits := fightMountBitsByCat[cat]; bits != 0 {
					if si := fieldIdxByCS(v.Class, csStateEnum); si >= 0 && si < len(v.Fields) &&
						v.Fields[si].Num != nil {
						*v.Fields[si].Num |= bits
					}
				}
			}
		}
	}
	for _, f := range v.Fields {
		if f.Val != nil {
			markFightMounted(f.Val, catOf)
		}
	}
	for _, it := range v.Items {
		markFightMounted(it, catOf)
	}
}
