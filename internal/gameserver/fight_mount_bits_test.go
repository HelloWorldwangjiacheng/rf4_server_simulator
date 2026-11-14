package gameserver

// 搏鱼期 4/22 挂载运行位注入测试。
// 增量表与官方搏鱼帧逐项对照（2026-11-12 lure2 抓包，见 spec Evidence 表）；
// 拟饵容器 markHookMounted 扩展、搏鱼推送形状（含/不含拟饵树）、
// buildMountedHookTree 拟饵整树/裸钩分叉都在本文件覆盖。

import (
	"context"
	"strings"
	"testing"
	"time"

	"rf4server/internal/logging"
	"rf4server/internal/proto"
	"rf4server/internal/tunnel"
	"rf4server/internal/wiregen"
)

// fightFlagTestObj 构造带数字 id 与基值状态位的假物品对象。
func fightFlagTestObj(t *testing.T, class string, numericID, base uint64) *proto.Value {
	t.Helper()
	ni, si := fieldIdxByCS(class, csNumericID), fieldIdxByCS(class, csStateEnum)
	if ni < 0 || si < 0 {
		t.Fatalf("类 %s 缺 iofbjlaadfg/hgaijieklek，增量表无法注入", class)
	}
	return wiregen.MustMakeObj(class, map[int]*proto.Value{
		ni: proto.U32(uint32(numericID)),
		si: proto.U32(uint32(base)),
	})
}

// objFlagsOf 读对象 hgaijieklek 当前值。
func objFlagsOf(t *testing.T, v *proto.Value) uint64 {
	t.Helper()
	si := fieldIdxByCS(v.Class, csStateEnum)
	if si < 0 || si >= len(v.Fields) || v.Fields[si].Num == nil {
		t.Fatalf("对象 %s 缺 %s 字段", v.Class, csStateEnum)
	}
	return *v.Fields[si].Num
}

// 增量表逐 cat 断言：官方搏鱼帧观测基值注入后逐项相等。
func TestFightMountBitsTableMatchesOfficial(t *testing.T) {
	cases := []struct {
		cat   int64
		class string
		base  uint64
		want  uint64
	}{
		{3, "cnolibojkao", 16896, 19968},  // 竿 +1024|2048
		{6, "dgjinoebdop", 25088, 28160},  // 轮 +1024|2048
		{11, "ohciikgjghe", 20992, 24064}, // 主线 +1024|2048
		{13, "oldfpclaabo", 21056, 24128}, // 前导 +1024|2048
		{14, "donkbnnmgjm", 20992, 24064}, // 丝锁 +1024|2048
		{17, "ioombppcnlh", 20992, 22016}, // 拟饵 +1024
		{12, "agedjipcnpe", 20992, 22016}, // 钩 +1024
		{7, "oiebifopill", 16896, 17920},  // 轮零件 +1024
		{8, "lcajgpjolbo", 16896, 17920},  // 轮零件 +1024
		{10, "plefjjahdgh", 16896, 17920}, // 轮零件 +1024
		{52, "ibinolcnogf", 16896, 17920}, // 轮零件 +1024
	}
	for _, tc := range cases {
		obj := fightFlagTestObj(t, tc.class, 777001, tc.base)
		markFightMounted(obj, func(int64) (int64, bool) { return tc.cat, true })
		if got := objFlagsOf(t, obj); got != tc.want {
			t.Errorf("cat%d %s flags=%d，期望官方观测值 %d", tc.cat, tc.class, got, tc.want)
		}
	}
}

// 旋钮（cat34 官方观测零增量）与未知品类不注入；无 iofbj 字段对象跳过。
func TestFightMountBitsSkipsKnobUnknownAndPlain(t *testing.T) {
	knob := fightFlagTestObj(t, "bndpebpblfk", 777002, 16896)
	markFightMounted(knob, func(int64) (int64, bool) { return 34, true })
	if got := objFlagsOf(t, knob); got != 16896 {
		t.Fatalf("旋钮 cat34 不应注入，实得 %d", got)
	}
	rod := fightFlagTestObj(t, "cnolibojkao", 777003, 16896)
	markFightMounted(rod, func(int64) (int64, bool) { return 0, false })
	if got := objFlagsOf(t, rod); got != 16896 {
		t.Fatalf("查不到 cat 不应注入，实得 %d", got)
	}
	plain := wiregen.MustMakeObj("gcfcdnfmnbh", map[int]*proto.Value{0: proto.U32(12)})
	markFightMounted(plain, func(int64) (int64, bool) { return 3, true }) // 仅要求不 panic
}

// markHookMounted 扩展：拟饵容器本体与嵌套钩全部补 1024（官方拟饵本体 22016）。
func TestMarkHookMountedFlagsLureContainerAndHooks(t *testing.T) {
	mk := func() *proto.Value {
		return wiregen.MustMakeObj("agedjipcnpe", map[int]*proto.Value{
			fieldIdxByCS("agedjipcnpe", csStateEnum): proto.U32(20992),
		})
	}
	h1, h2 := mk(), mk()
	container := wiregen.MustMakeObj("ioombppcnlh", map[int]*proto.Value{
		0:                                        proto.Args(proto.S("60"), h1, h2),
		fieldIdxByCS("ioombppcnlh", csStateEnum): proto.U32(20992),
	})
	markHookMounted(container)
	if got := objFlagsOf(t, container); got != 22016 {
		t.Fatalf("拟饵容器本体 flags=%d，期望 22016", got)
	}
	for i, h := range []*proto.Value{h1, h2} {
		if got := objFlagsOf(t, h); got != 22016 {
			t.Fatalf("嵌套钩[%d] flags=%d，期望 22016", i, got)
		}
	}
}

// 路亚搏鱼推送：含拟饵树（ioombppcnlh 顶层、钩带 1024），竿/线/轮带运行位。
func TestPush422FightSyncLureIncludesLureTree(t *testing.T) {
	srv, db := newDetachTestServer(t)
	ctx := context.Background()
	const uid = int64(1000001)
	rod, err := srv.CreateItem(ctx, uid, "spin_10032_S60L", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	line, err := srv.CreateItem(ctx, uid, "mono_15097", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	reel, err := srv.CreateItem(ctx, uid, "bclp_5004", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	lure, err := srv.CreateItem(ctx, uid, "crankbaits_2171", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	sess := newProbeSess(srv)
	runRodSet(t, srv, sess, rod.GUID, line.GUID, 0)
	mountLure(t, db, srv, rod.GUID, lure.GUID)
	st := srv.stateFor(uid)
	st.mu.Lock()
	st.GearGuid = rod.GUID
	st.mu.Unlock()

	conn, peer := cleanupTestTunnel(t, "fight-sync-lure")
	live := registerBiteTestSession(t, srv, 401, conn)
	received := receiveTestPush(peer, 4, 22)
	live.Push4_22FightSync(rod.GUID, []string{reel.GUID})

	var env *proto.Envelope
	select {
	case env = <-received:
	case <-time.After(2 * time.Second):
		t.Fatal("搏鱼推送超时")
	}
	dec, _, err := proto.DecodeValue(env.Body, 0, srv.Table())
	if err != nil || dec.ArgCodeStr() != "61" {
		t.Fatalf("4/22 应为 args(61): %v", err)
	}
	byClass := map[string]*proto.Value{}
	for _, it := range dec.Items {
		if it != nil {
			byClass[it.Class] = it
		}
	}
	rodTree, lineTree, lureTree, reelTree := byClass["cnolibojkao"], byClass["ohciikgjghe"], byClass["ioombppcnlh"], byClass["dgjinoebdop"]
	if rodTree == nil || lineTree == nil || lureTree == nil || reelTree == nil {
		t.Fatalf("搏鱼推送应含竿/线/拟饵树/轮四元素，实得 %v", classList(dec.Items))
	}
	for name, tree := range map[string]*proto.Value{"竿": rodTree, "线": lineTree, "轮": reelTree} {
		if got := objFlagsOf(t, tree); got&(1024|2048) != 1024|2048 {
			t.Fatalf("%s flags=%d 缺运行位 1024|2048", name, got)
		}
	}
	if got := objFlagsOf(t, lureTree); got&1024 == 0 {
		t.Fatalf("拟饵本体 flags=%d 缺 1024", got)
	}
	if len(lureTree.Fields) == 0 || lureTree.Fields[0].Val == nil || len(lureTree.Fields[0].Val.Items) == 0 {
		t.Fatal("推送拟饵树缺出厂钩")
	}
	for i, hook := range lureTree.Fields[0].Val.Items {
		if hook == nil || hook.Class != "agedjipcnpe" {
			t.Fatalf("拟饵树钩[%d] 形状错误", i)
		}
		if got := objFlagsOf(t, hook); got&1024 == 0 {
			t.Fatalf("拟饵树钩[%d] flags=%d 缺 1024", i, got)
		}
	}
}

// 底钓搏鱼推送不含拟饵树（回归保护）；钩帧保持裸钩。
func TestPush422FightSyncBottomRigNoLureTree(t *testing.T) {
	srv, _ := newDetachTestServer(t)
	ctx := context.Background()
	const uid = int64(1000001)
	rod, err := srv.CreateItem(ctx, uid, "feeder_10125_FD360", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	if !srv.rigSetType(ctx, uid, rod.GUID, 12) {
		t.Fatal("rigSetType 失败")
	}
	line, err := srv.CreateItem(ctx, uid, "mono_15094", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	hook, err := srv.CreateItem(ctx, uid, "c_hook_20712", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	sess := newProbeSess(srv)
	runRodSet(t, srv, sess, rod.GUID, line.GUID, 0)
	runRodSet(t, srv, sess, rod.GUID, hook.GUID, 0)
	st := srv.stateFor(uid)
	st.mu.Lock()
	st.GearGuid = rod.GUID
	st.mu.Unlock()

	// 中鱼钩帧：无拟饵时保持独立钩行裸钩形状（回归保护）。
	hookItems, err := srv.buildFightItems(ctx, uid, false)
	if err != nil || len(hookItems) != 1 {
		t.Fatalf("钩帧应 1 个对象: n=%d err=%v", len(hookItems), err)
	}
	if hookItems[0].Class != "agedjipcnpe" {
		t.Fatalf("底钓钩帧应保持裸钩 agedjipcnpe，实得 %s", hookItems[0].Class)
	}

	conn, peer := cleanupTestTunnel(t, "fight-sync-bottom")
	live := registerBiteTestSession(t, srv, 402, conn)
	received := receiveTestPush(peer, 4, 22)
	live.Push4_22FightSync(rod.GUID, nil)

	var env *proto.Envelope
	select {
	case env = <-received:
	case <-time.After(2 * time.Second):
		t.Fatal("搏鱼推送超时")
	}
	dec, _, err := proto.DecodeValue(env.Body, 0, srv.Table())
	if err != nil {
		t.Fatal(err)
	}
	for _, it := range dec.Items {
		if it != nil && it.Class == "ioombppcnlh" {
			t.Fatal("底钓搏鱼推送不应含拟饵树")
		}
	}
	var rodTree *proto.Value
	for _, it := range dec.Items {
		if it != nil && it.Class == "cnolibojkao" {
			rodTree = it
		}
	}
	if rodTree == nil {
		t.Fatal("底钓搏鱼推送缺竿树")
	}
	if got := objFlagsOf(t, rodTree); got&(1024|2048) != 1024|2048 {
		t.Fatalf("底钓竿 flags=%d 缺运行位 1024|2048", got)
	}
}

// buildMountedHookTree 路亚分支：内置钩（含出厂钩）返回拟饵整树；
// 非拟饵内置的 GUID 不命中。
func TestLureContainsHookAndWholeTree(t *testing.T) {
	srv, db := newDetachTestServer(t)
	ctx := context.Background()
	const uid = int64(1000001)
	rod, err := srv.CreateItem(ctx, uid, "spin_10032_S60L", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	lure, err := srv.CreateItem(ctx, uid, "crankbaits_2171", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	mountLure(t, db, srv, rod.GUID, lure.GUID)
	st := srv.stateFor(uid)
	st.mu.Lock()
	st.GearGuid = rod.GUID
	st.mu.Unlock()

	lureRow, err := db.GetItemByGUID(ctx, lure.GUID)
	if err != nil || lureRow == nil {
		t.Fatal(err)
	}
	fields, err := FieldsFromJSON(lureRow.FieldsJSON)
	if err != nil || len(fields) == 0 || fields[0].Val == nil || len(fields[0].Val.Items) == 0 {
		t.Fatal("拟饵缺出厂钩数组")
	}
	factoryHook := lureHookItemGUIDs(fields[0].Val.Items)[0]
	if !srv.lureContainsHook(ctx, lure.GUID, factoryHook) {
		t.Fatal("出厂钩应判定为拟饵内置")
	}
	if srv.lureContainsHook(ctx, lure.GUID, "00000000000000000000000000000000") {
		t.Fatal("随机 GUID 不应判定为拟饵内置")
	}
	tree := srv.buildMountedHookTree(ctx, rod.GUID)
	if tree == nil || tree.Class != "ioombppcnlh" {
		t.Fatalf("路亚中鱼钩帧应为拟饵整树 ioombppcnlh，实得 %v", tree)
	}
	// 钩物理链路（mountedHookDef 强度/钩号）依赖单钩树语义。
	sub := srv.mountedHookSubTree(ctx, rod.GUID, factoryHook)
	if sub == nil || sub.Class != "agedjipcnpe" {
		t.Fatalf("mountedHookSubTree 应返回单钩 agedjipcnpe，实得 %v", sub)
	}
}

// classList 调试用：4/22 元素类列表。
func classList(items []*proto.Value) []string {
	out := make([]string, 0, len(items))
	for _, it := range items {
		if it != nil {
			out = append(out, it.Class)
		}
	}
	return out
}

// readFightSyncPush 从测试隧道读下一帧 4/22 并解码；只报告结果，不触碰 testing.T
// （供收集协程调用，协程里禁止 t.Fatal）。
func readFightSyncPush(srv *Server, peer *tunnel.Conn) (*proto.Value, error) {
	for {
		kind, _, payload, err := peer.ReadRecord()
		if err != nil {
			return nil, err
		}
		if kind != tunnel.TypeData {
			continue
		}
		env, ok := proto.ParseEnvelope(payload)
		if !ok || env.Main != 4 || env.Sub != 22 {
			continue
		}
		v, _, derr := proto.DecodeValue(env.Body, 0, srv.Table())
		if derr != nil {
			return nil, derr
		}
		if v.ArgCodeStr() != "61" {
			return nil, &wireErrShim{msg: "4/22 应为 args(61)，实得 " + v.ArgCodeStr()}
		}
		return v, nil
	}
}

// wireErrShim 测试本地错误类型。
type wireErrShim struct{ msg string }

func (e *wireErrShim) Error() string { return e.msg }

// waitFightFrame 带超时从收集协程收一帧 4/22。
func waitFightFrame(t *testing.T, frames <-chan *proto.Value) *proto.Value {
	t.Helper()
	select {
	case v, ok := <-frames:
		if !ok || v == nil {
			t.Fatal("收集协程提前结束，未收到 4/22")
		}
		return v
	case <-time.After(3 * time.Second):
		t.Fatal("等待 4/22 超时")
	}
	return nil
}

// 14/11 中鱼路径集成测试：中鱼确认当刻客户端必须收到两帧 4/22——
// 第一帧钩帧（路亚=拟饵整树），第二帧全树运行位同步（竿/线/轮 1024|2048、
// 拟饵树在）。客户端搏鱼 ctor 一次性锁定挂载态，运行位不能等结算才发。
func TestHookConfirmSendsHookFrameThenFightSync(t *testing.T) {
	srv, db := newDetachTestServer(t)
	ctx := context.Background()
	const uid = int64(1000001)
	rod, err := srv.CreateItem(ctx, uid, "spin_10032_S60L", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	line, err := srv.CreateItem(ctx, uid, "mono_15097", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	reel, err := srv.CreateItem(ctx, uid, "bclp_5004", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	lure, err := srv.CreateItem(ctx, uid, "crankbaits_2171", "backpack", 1)
	if err != nil {
		t.Fatal(err)
	}
	sess := newProbeSess(srv)
	runRodSet(t, srv, sess, rod.GUID, line.GUID, 0)
	runRodSet(t, srv, sess, rod.GUID, reel.GUID, 0)
	mountLure(t, db, srv, rod.GUID, lure.GUID)
	st := srv.stateFor(uid)
	st.mu.Lock()
	st.GearGuid = rod.GUID
	st.RigType = 5 // 路亚
	st.CastActive = true
	st.InWater = true
	st.Pending = &RolledFish{FishGUID: strings.Repeat("ab", 16), Species: "perch",
		Grade: 2, WeightG: 321, LengthM: 0.24, BiteQuality: "solid", HookHoldP: 1}
	st.mu.Unlock()

	conn, peer := cleanupTestTunnel(t, "hook-fight-sync")
	live := registerBiteTestSession(t, srv, 404, conn)
	// net.Pipe 无缓冲：推送写入会阻塞等读者，必须在调用 handler 前启动收集协程，
	// 否则 handler 的第一帧 4/22 永远写不出去（测试死锁）。
	frames := make(chan *proto.Value, 4)
	go func() {
		defer close(frames)
		for i := 0; i < 2; i++ {
			v, err := readFightSyncPush(srv, peer)
			if err != nil {
				return
			}
			frames <- v
		}
	}()
	if _, ok := hFishingHooked(&Ctx{Sess: live, Main: 14, Sub: 11, Log: logging.Discard()}); !ok {
		t.Fatal("14/11 未处理")
	}

	// 第一帧：钩帧（路亚=拟饵整树 +1024）。
	hookFrame := waitFightFrame(t, frames)
	if hookFrame.ArgCount() != 1 || hookFrame.Items[0] == nil || hookFrame.Items[0].Class != "ioombppcnlh" {
		t.Fatalf("14/11 第一帧应为钩帧（拟饵整树 1 元素），实得 %v", classList(hookFrame.Items))
	}
	lureInHookFrame := hookFrame.Items[0]
	if got := objFlagsOf(t, lureInHookFrame); got&1024 == 0 {
		t.Fatalf("钩帧拟饵本体 flags=%d 缺 1024", got)
	}

	// 第二帧：全树运行位同步（竿+线+拟饵树，extras 轮）。
	fightFrame := waitFightFrame(t, frames)
	byClass := map[string]*proto.Value{}
	for _, it := range fightFrame.Items {
		if it != nil {
			byClass[it.Class] = it
		}
	}
	rodTree, lineTree, lureTree, reelTree := byClass["cnolibojkao"], byClass["ohciikgjghe"], byClass["ioombppcnlh"], byClass["dgjinoebdop"]
	if rodTree == nil || lineTree == nil || lureTree == nil || reelTree == nil {
		t.Fatalf("14/11 全树同步应含竿/线/拟饵树/轮，实得 %v", classList(fightFrame.Items))
	}
	for name, tree := range map[string]*proto.Value{"竿": rodTree, "线": lineTree, "轮": reelTree} {
		if got := objFlagsOf(t, tree); got&(1024|2048) != 1024|2048 {
			t.Fatalf("14/11 %s flags=%d 缺运行位 1024|2048", name, got)
		}
	}
	if got := objFlagsOf(t, lureTree); got&1024 == 0 {
		t.Fatalf("14/11 拟饵本体 flags=%d 缺 1024", got)
	}
	for i, hook := range lureTree.Fields[0].Val.Items {
		if got := objFlagsOf(t, hook); got&1024 == 0 {
			t.Fatalf("14/11 拟饵树钩[%d] flags=%d 缺 1024", i, got)
		}
	}
}
