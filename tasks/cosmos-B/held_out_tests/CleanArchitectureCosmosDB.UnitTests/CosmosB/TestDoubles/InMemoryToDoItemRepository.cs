using Ardalis.Specification;
using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Core.Interfaces;
using CleanArchitectureCosmosDB.Core.Specifications.Base;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB.TestDoubles
{
    /// <summary>
    ///     Hand-written in-memory fake of IToDoItemRepository for unit testing handlers
    ///     and specifications without a live Cosmos DB. Specifications are applied with
    ///     Ardalis.Specification's in-memory Evaluate().
    ///
    ///     The store keeps detached *copies*, and reads return copies, so the only way a
    ///     mutation survives is an explicit UpdateItemAsync — exactly like a real
    ///     document store. A handler that mutates the loaded entity but forgets to
    ///     persist it will therefore be caught.
    /// </summary>
    public class InMemoryToDoItemRepository : IToDoItemRepository
    {
        private readonly Dictionary<string, ToDoItem> _store = new Dictionary<string, ToDoItem>();

        // Copy a ToDoItem without sharing the reference. IsCompleted has a private
        // setter, so the completed flag is restored through MarkComplete().
        private static ToDoItem Clone(ToDoItem item)
        {
            ToDoItem copy = new ToDoItem
            {
                Id = item.Id,
                Category = item.Category,
                Title = item.Title
            };
            if (item.IsCompleted)
            {
                copy.MarkComplete();
            }
            return copy;
        }

        public Task<ToDoItem> GetItemAsync(string id)
        {
            _store.TryGetValue(id, out ToDoItem entity);
            return Task.FromResult(entity == null ? null : Clone(entity));
        }

        public Task AddItemAsync(ToDoItem item)
        {
            if (string.IsNullOrEmpty(item.Id))
            {
                item.Id = $"{item.Category}:{Guid.NewGuid()}";
            }
            _store[item.Id] = Clone(item);
            return Task.CompletedTask;
        }

        public Task UpdateItemAsync(string id, ToDoItem item)
        {
            _store[id] = Clone(item);
            return Task.CompletedTask;
        }

        public Task DeleteItemAsync(string id)
        {
            _store.Remove(id);
            return Task.CompletedTask;
        }

        public Task<IEnumerable<ToDoItem>> GetItemsAsync(string query)
        {
            return Task.FromResult<IEnumerable<ToDoItem>>(_store.Values.Select(Clone).ToList());
        }

        public Task<IEnumerable<ToDoItem>> GetItemsAsync(ISpecification<ToDoItem> specification)
        {
            List<ToDoItem> results = Apply(specification).Select(Clone).ToList();
            return Task.FromResult(results.AsEnumerable());
        }

        public Task<int> GetItemsCountAsync(ISpecification<ToDoItem> specification)
        {
            int count = Apply(specification).Count();
            return Task.FromResult(count);
        }

        // Evaluate a specification in-memory using the same evaluator the repository uses.
        private IQueryable<ToDoItem> Apply(ISpecification<ToDoItem> specification)
        {
            CosmosDbSpecificationEvaluator<ToDoItem> evaluator = new CosmosDbSpecificationEvaluator<ToDoItem>();
            return evaluator.GetQuery(_store.Values.AsQueryable(), specification);
        }
    }
}
