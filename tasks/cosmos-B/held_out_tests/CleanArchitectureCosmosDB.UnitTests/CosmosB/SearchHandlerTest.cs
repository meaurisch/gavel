using AutoMapper;
using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.Core.Specifications.Interfaces;
using CleanArchitectureCosmosDB.UnitTests.CosmosB.TestDoubles;
using CleanArchitectureCosmosDB.WebAPI.Models.ToDoItem;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB
{
    /// <summary>
    ///     End-to-end at the handler level: the search query's completion filter must
    ///     reach both the record specification (the returned page) and the aggregation
    ///     specification (TotalRecordsMatched). A handler that adds the property but
    ///     forgets to pass it through to either spec is caught here.
    /// </summary>
    public class SearchHandlerTest
    {
        private static IMapper BuildMapper()
        {
            MapperConfiguration config = new MapperConfiguration(cfg =>
                cfg.CreateMap<ToDoItem, ToDoItemModel>());
            return config.CreateMapper();
        }

        private static async Task<InMemoryToDoItemRepository> SeededRepo()
        {
            InMemoryToDoItemRepository repo = new InMemoryToDoItemRepository();

            ToDoItem done = new ToDoItem() { Id = "work:1", Category = "work", Title = "Done item" };
            done.MarkComplete();
            await repo.AddItemAsync(done);
            await repo.AddItemAsync(new ToDoItem() { Id = "work:2", Category = "work", Title = "Open item A" });
            await repo.AddItemAsync(new ToDoItem() { Id = "home:3", Category = "home", Title = "Open item B" });

            return repo;
        }

        private static Search.SearchToDoItemQuery Query(bool? isCompleted)
        {
            return new Search.SearchToDoItemQuery
            {
                Start = 0,
                PageSize = -1, // disable pagination, return all matches
                SortColumn = "title",
                SortDirection = SortDirection.Ascending,
                IsCompletedFilter = isCompleted
            };
        }

        [Fact]
        public async Task IsCompletedFilterTrue_ReturnsAndCountsOnlyCompleted()
        {
            InMemoryToDoItemRepository repo = await SeededRepo();
            Search.QueryHandler handler = new Search.QueryHandler(repo, BuildMapper());

            Search.QueryResponse response = await handler.Handle(Query(true), CancellationToken.None);

            Assert.Single(response.Resource);
            Assert.Equal("work:1", response.Resource.Single().Id);
            Assert.Equal(1, response.TotalRecordsMatched);
        }

        [Fact]
        public async Task IsCompletedFilterFalse_ReturnsAndCountsOnlyIncomplete()
        {
            InMemoryToDoItemRepository repo = await SeededRepo();
            Search.QueryHandler handler = new Search.QueryHandler(repo, BuildMapper());

            Search.QueryResponse response = await handler.Handle(Query(false), CancellationToken.None);

            Assert.Equal(2, response.Resource.Count());
            Assert.Equal(2, response.TotalRecordsMatched);
            Assert.DoesNotContain("work:1", response.Resource.Select(x => x.Id));
        }

        [Fact]
        public async Task IsCompletedFilterNull_ReturnsAndCountsEverything()
        {
            InMemoryToDoItemRepository repo = await SeededRepo();
            Search.QueryHandler handler = new Search.QueryHandler(repo, BuildMapper());

            Search.QueryResponse response = await handler.Handle(Query(null), CancellationToken.None);

            Assert.Equal(3, response.Resource.Count());
            Assert.Equal(3, response.TotalRecordsMatched);
        }
    }
}
