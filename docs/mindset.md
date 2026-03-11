**RVT-Swarm**

**Recoverability-Verified Topological Swarm Control**

Ý tưởng cốt lõi:  
thay vì học "safe hay unsafe ngay bây giờ", ta học một **recoverability field** trên đồ thị cục bộ của swarm, tức một giá trị cho biết:  
**"nếu chọn control + tái cấu trúc formation như thế này, swarm có còn khả năng đi qua vùng hiện tại, tránh va chạm, và tái lập formation tube trong H bước tới hay không?"**

Nó gồm 3 thành phần gắn chặt với nhau:

**1) Recoverability Field Network (RFN)**

Một GNN học xấp xỉ **recoverability margin** chứ không chỉ collision margin. Input là local graph state + obstacle dynamics + goal context + current formation descriptor. Output là một lower bound của khả năng còn "cứu được" trong horizon H. Dữ liệu huấn luyện không lấy từ label va chạm tức thời, mà từ short-horizon reach-avoid-recover rollouts hoặc local OCP/MPC snippets: positive nếu có thể tránh va chạm **và** quay lại formation tube/goal-progress tube trong H bước; negative nếu không. Ý tưởng này gần viability / reachability, nhưng chưa không thấy paper gần đây nào biến nó thành **distributed recoverability certificate cho swarm formation control**; các nhánh gần nhất mới dừng ở viability kernel nói chung, learned CBF, hoặc deadlock-free navigation.

**2) Topological Action Space**

Không xem action chỉ là vận tốc. Mỗi robot còn tham gia vào một **topological action** cục bộ: giữ đội hình, co giãn, xếp hàng, tách subteam, nhập team lại. Khác với các paper adaptive formation gần đây vốn hay chọn từ vài pattern định sẵn hoặc framework phân tầng, ở đây topological action được quyết định trực tiếp bởi policy nhưng bị ràng buộc bởi recoverability margin. Tôi đã thấy adaptive formation, formation reconfiguration, environment-adaptive confined-space formation, và cả subteaming rất gần hướng này, nhưng chưa thấy cái nào dùng **recoverability-verified topology switching** làm cơ chế điều khiển chính.

**3) Counterfactual Topology Selector**

Mỗi robot không chỉ hỏi "action hiện tại có an toàn không?" mà hỏi thêm:

- nếu giữ topology hiện tại thì recoverability margin là bao nhiêu?
- nếu co đội hình?
- nếu đề xuất line mode?
- nếu tách subteam?  
    Policy sẽ đánh giá vài lựa chọn topology-control cục bộ bằng RFN và chọn phương án có **recoverability margin dương lớn nhất** dưới ràng buộc tiến tới goal. Đây là "counterfactual" theo nghĩa ra quyết định dựa trên các topology giả định song song. Tôi thấy counterfactual đã được dùng cho fairness/credit assignment trong multi-robot navigation, nhưng chưa thấy dùng để chọn **formation topology theo recoverability**.

đề xuất kiến trúc đầy đủ như sau:

**Quan sát cục bộ:** lidar / occupancy patch, relative neighbors, local obstacle velocity cues, goal direction, formation tube error, bottleneck score.  
**Encoder:** heterogeneous graph transformer hoặc equivariant GNN.  
**Ba đầu ra:**

- u_i: control primitive của robot i
- τ_i: logits cho topological action cục bộ
- r_i: recoverability margin cục bộ  
    **Consensus layer:** neighborhood agreement cho topological action để tránh split vô tổ chức.  
    **Shield:** chỉ can thiệp nếu tất cả lựa chọn có recoverability âm; khi đó chọn action tối thiểu hóa vi phạm và tối đa hóa khả năng quay lại tube.

Vì sao hướng này **đủ mới**? Vì các paper gần nhất mới giải quyết từng mảnh:

- graph safety certificates / learned CBF cho an toàn phi tập trung, nhưng không theo recoverability-to-recover-formation.
- adaptive formation / subteaming / confined spaces, nhưng thiếu safety certificate kiểu recoverability.
- diffusion/generative planning cho swarm, nhưng không gắn recoverability certificate làm lớp quyết định topology.
- conformal/uncertainty-aware safe control, nhưng chưa tập trung vào formation topology switching phi tập trung ở swarm scale.

**bộ lõi**:  
**decentralized formation control + topology adaptation/subteaming + recoverability certificate + counterfactual topology selection**.

**Khả thi về mặt học máy**

RFN không phải học toàn bộ joint-state viability của cả swarm, cái đó quá lớn. Nó chỉ học **local recoverability surrogate** trên ego-neighborhood graph với horizon ngắn H và formation-tube objective. Điều này rất giống cách GCBF+ dùng graph locality để scale safety certificates, nên về mặt học hàm trên đồ thị là hoàn toàn khả thi. Dữ liệu được tạo ra bằng:

- expert MPC/local planner cho những neighborhood khó,
- backward rollouts từ near-failure states,
- và hard-negative mining ở bottleneck.

**Khả thi về mặt điều khiển**

Nếu RFN được huấn luyện để lower-bound recoverability margin, thì shield chỉ cần đảm bảo chọn action/topology sao cho margin không âm hoặc giảm âm ít nhất. Đây là tinh thần gần với CBF/viability: duy trì hệ trong một **recoverable set** thay vì chỉ safe set tức thời. Ta không cần chứng minh optimality toàn cục; chỉ cần chứng minh một mệnh đề kiểu:

nếu mọi robot duy trì local recoverability margin trên ngưỡng và communication graph đủ phủ lân cận va chạm, thì joint system tránh được collision trong H bước và có một policy quay lại formation tube.  
Đây là dạng theorem đủ mạnh cho Q1 nếu viết cẩn thận. Nó còn hợp với trend dùng local certificate để scale multi-agent safety.

**Khả thi về thực nghiệm**

Bài này rất hợp benchmark mà cộng đồng đang quan tâm:

- cluttered fields
- narrow passages/doorways
- moving obstacles
- large-N scaling
- delayed communication / limited sensing  
    Đây đúng là các regime mà paper adaptive formation, deadlock-free navigation, và safe multi-robot learning đều dùng để phơi ra weakness của phương pháp cũ.

**Claim paper nên hướng tới**

Nếu làm đúng, paper của bạn không nên claim "best success" ngay từ đầu. Claim nên là:

**"First recoverability-verified decentralized swarm formation controller that jointly reasons over control and topology adaptation."**

Và 3 hypothesis cần chứng minh là:

- **Higher liveness/progress** than instantaneous-safety shields in bottlenecks.
- **Lower irreversible formation collapse** than plain adaptive formation baselines.
- **Better safety-progress trade-off** than graph-CBF-only or diffusion-only baselines.

Các baseline nên so:

- GCBF+ / MA-ICBF style safe controller
- AFOR / STAF / environment-adaptive formation baselines
- diffusion-based planners như SwarmDiff / ReDiG / MMD
- deadlock-free discrete-time CBF navigation in narrow spaces

Tôi gợi ý objective online như sau:

\\\[

\\max_{u,\\tau}\\quad \\alpha \\cdot \\text{goal-progress}

\+ \\beta \\cdot \\text{formation-tube reward}

\+ \\gamma \\cdot \\text{recoverability margin}

\\\]

\`\`\`latex

\\\[

\\text{s.t.}

\\\]

\`\`\`latex

\\\[

\\hat{R}\_i(G_t, u, \\tau) \\ge 0

\\quad \\forall i \\in \\mathcal{N}\_{\\mathrm{critical}}

\\\]

Trong đó τ là topological action; \\hat R_i là recoverability margin từ RFN. Nếu không có lựa chọn nào thỏa, shield giải một QP nhỏ để tối thiểu hóa tổng vi phạm margin và giữ tiến độ tối đa.

**Tên paper có thể dùng**

- **RVT-Swarm: Recoverability-Verified Topological Control for Decentralized Swarm Formation**
- **ReFormSafe: Recoverability-Aware Formation Reconfiguration for Safe Swarm Navigation**
- **VITA-Swarm: Viability-Informed Topology Adaptation for Safe Multi-Robot Formation Control**