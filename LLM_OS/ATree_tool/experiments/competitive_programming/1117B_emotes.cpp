/**
 * Problem: Codeforces 1117B - Emotes
 * Contest: Educational Codeforces Round 60 (Rated for Div. 2)
 *
 * Algorithm:
 * To maximize total happiness using at most k consecutive identical emotes:
 * 1. Find the largest emote value (max1) and second largest emote value (max2).
 * 2. Form blocks of size (k + 1): use max1 k times, then max2 1 time.
 *    Block value = k * max1 + max2.
 * 3. Total complete blocks = m / (k + 1).
 * 4. Remainder emotes = m % (k + 1), each taking value max1.
 * 5. Total = (m / (k + 1)) * (k * max1 + max2) + (m % (k + 1)) * max1.
 *
 * Complexity:
 * - Time: O(n log n) or O(n)
 * - Space: O(n)
 */

#include <iostream>
#include <vector>
#include <algorithm>

using namespace std;

void solve() {
    long long n, m, k;
    if (!(cin >> n >> m >> k)) return;
    
    vector<long long> a(n);
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
    }
    
    sort(a.rbegin(), a.rend());
    long long max1 = a[0];
    long long max2 = a[1];
    
    long long block_size = k + 1;
    long long full_blocks = m / block_size;
    long long remainder = m % block_size;
    
    long long total_happiness = full_blocks * (k * max1 + max2) + remainder * max1;
    cout << total_happiness << "\n";
}

int main() {
    // Fast I/O
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    solve();
    
    return 0;
}
