Git
├─ 基础操作
│  ├─ git init                 # 新建本地git仓库
│  ├─ git clone <url>          # 拉取远程仓库
│  ├─ git add [文件|.]         # 加入暂存区
│  ├─ git status               # 查看状态
│  ├─ git diff [--staged]      # 差异对比
│  └─ git commit [-m|--amend]  # 提交到本地仓库
├─ 分支
│  ├─ git branch [-a/-d/-D]
│  ├─ git checkout [-b] / git switch [-c]
│  ├─ git merge [--no-ff]
│  └─ git rebase [-i]
├─ 远程仓库
│  ├─ git remote [-v/add/rm]
│  ├─ git fetch
│  ├─ git pull [--rebase]
│  └─ git push [-u/--force]
├─ 日志查看
│  ├─ git log [--oneline/--graph/-n]
│  └─ git show <commit-id>
├─ 撤销/回滚（高危注意）
│  ├─ git reset [--soft/--mixed/--hard]
│  ├─ git restore [--staged]
│  ├─ git revert
│  └─ git clean -fd
├─ 标签tag
│  ├─ git tag [-a/-d]
│  └─ git push origin [--tags]
└─ 储藏stash
   ├─ git stash
   ├─ git stash list
   ├─ git stash pop / apply
   └─ git stash drop
